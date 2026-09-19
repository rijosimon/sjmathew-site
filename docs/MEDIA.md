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

1. **Create the Space** (DigitalOcean → Spaces Object Storage → Create): region **Singapore
   (sgp1)**, name `sjmathew-media`. Turn on the **CDN**, and choose **Restrict File Listing** so
   people can fetch files but not list them. The plan is $5 a month and includes 250 GiB.
2. **Create an access key** (Spaces → Access Keys → Generate New Key). Keep the secret private; you
   only see it once.
3. **Tell rclone about it.** Run `rclone config`, choose `n` (new remote), name it `sjmathew`, type
   `s3`, provider `DigitalOcean Spaces`, choose "Enter AWS credentials in the next step", and paste
   the key and secret when asked. Endpoint: `sgp1.digitaloceanspaces.com`. ACL: `public-read`.

## Upload

```bash
rclone copy ~/Workspace/sjmathew-media/out sjmathew:sjmathew-media \
  --transfers 8 --checksum --progress \
  --header-upload "Cache-Control: public, max-age=31536000"
```

It can be stopped and started again; files that already arrived are skipped. Expect a few hours,
depending on your upload speed. Then confirm nothing is missing or damaged:

```bash
rclone check ~/Workspace/sjmathew-media/out sjmathew:sjmathew-media --one-way
```

## Connect the site

The Space's CDN address looks like `https://sjmathew-media.sgp1.cdn.digitaloceanspaces.com`.
Set it as the site's media address, in `.do/app.yaml`:

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
