# The media library

The site's audio, video, downloads and pictures are not in this repository. They live in a
DigitalOcean Space and the pages link to them by **key** (the file's path inside the Space, for
example `audio/ykt/class-08.mp3`). `PUBLIC_MEDIA_BASE_URL` says where the Space is served from.

## What is ready

The old site's files were copied, renamed and converted on a Mac into
`~/Workspace/sjmathew-media/out/` (about 90 GB, 1,045 files). `data/media-map.json` lists every file
with its size and MD5 checksum. Only files that a published page links to were carried over
(`data/media-report.md` explains what was left behind and why).

| Folder in the Space | What it holds |
|---|---|
| `audio/` | MP3 tracks played on the message pages (also the theme's old audio folder under `audio/theme/`) |
| `downloads/audio/`, `downloads/video/` | ZIP files offered as downloads |
| `video/` | MP4 videos that play on the page (converted from the old AVI files and zipped videos) |
| `library/` | E-books, e-tracts and tracts (PDF) |
| `images/` | Covers and pictures |

## One-time setup (you)

1. **Create the bucket.** In the DigitalOcean panel: **Spaces Object Storage → Create Bucket**.
   Region **Singapore (sgp1)**, name `sjmathew-media` (3 to 63 characters; if it is taken, add a
   suffix). The plan is $5 a month and includes 250 GiB.
2. **Turn on the CDN.** Open the bucket → **Settings** tab → **CDN** → **Edit** → **Enable CDN**.
   Note the CDN address it shows, like `https://sjmathew-media.sgp1.cdn.digitaloceanspaces.com`.
3. **Create an access key.** **Spaces Object Storage → Access Keys** tab → **Create Access Key**.
   If it offers per-bucket access, give it read, write and delete on `sjmathew-media` only. The
   secret is shown once: copy it into your password manager. Keys can only be created in the panel,
   not from the command line, and should never be pasted into chat or committed.
4. **Tell rclone about it.** Run `rclone config` and answer: `n` (new remote), name `sjmathew`,
   storage `s3`, provider `DigitalOcean`, `env_auth` false, then your access key and secret,
   endpoint `sgp1.digitaloceanspaces.com`, ACL `public-read`, and accept the defaults for the rest.
   The result in `~/.config/rclone/rclone.conf` looks like:
   ```ini
   [sjmathew]
   type = s3
   provider = DigitalOcean
   access_key_id = <your key>
   secret_access_key = <your secret>
   endpoint = sgp1.digitaloceanspaces.com
   acl = public-read
   ```
   Test it with the bucket's name: `rclone lsd sjmathew:sjmathew-media` should finish without an error.
   (`rclone lsd sjmathew:` on its own can fail with 403 AccessDenied when the key is limited to one
   bucket; that is expected.)

## Upload

```bash
caffeinate -i rclone copy ~/Workspace/sjmathew-media/out sjmathew:sjmathew-media \
  --s3-no-check-bucket --s3-chunk-size 32M --transfers 8 --checksum --progress \
  --header-upload "Cache-Control: public, max-age=31536000"
```

`caffeinate -i` keeps the Mac awake while it runs. It can be stopped and started again; files that already arrived are skipped. Expect a few hours,
depending on your upload speed. Then confirm nothing is missing or damaged:

```bash
rclone check ~/Workspace/sjmathew-media/out sjmathew:sjmathew-media --one-way --s3-no-check-bucket
```

## Connect the site

The Space's CDN address looks like `https://sjmathew-media.sgp1.cdn.digitaloceanspaces.com`.
Set it as the site's media address in `.do/app.yaml` (I can do this for you once the upload has been checked):

```yaml
static_sites:
  - name: web
    envs:
      - key: PUBLIC_MEDIA_BASE_URL
        value: https://sjmathew-media.sgp1.cdn.digitaloceanspaces.com
        scope: BUILD_TIME
```

Then push. When the domain moves to DigitalOcean's name servers, a custom address such as
`https://media.sjmathew.com` can replace it (Space → Settings → CDN → custom subdomain).

## Checking the site against the library

```bash
npm run build
python3 scripts/check_site.py        # links between pages, and every /media/ file exists locally
```

## Rebuilding the library from the old server

The scripts in `scripts/migration/` do this end to end and are safe to run again (they only read
from the old server): `media_manifest.py`, `media_refs.py`, `build_media_plan.py`,
`export_content.py`, `process_media.py --videos`. Working data goes to `data/raw/` (not committed).
