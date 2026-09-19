# Editing the site

New messages, readings, books and tracts are added in a web editor at `/admin/` (Decap CMS). It does
not change the live site directly: every save is a commit to the GitHub repository, and every commit
to `main` rebuilds and publishes the site (usually within two minutes).

## How the pieces fit

| Piece | What it holds | Where |
|---|---|---|
| Text and settings | Titles, dates, languages, the list of parts, download buttons, article text | `src/content/` in this repository (edited through `/admin/`) |
| Files | MP3s, MP4s, ZIPs, PDFs, pictures | The media library (DigitalOcean Spaces), not in the repository |
| The site | Pages, players, search | Built from the repository by DigitalOcean App Platform |

The editor never uploads audio or video. It stores the **file path** of each file (for example
`audio/ykt/class-08.mp3`), and the site turns that into the file's address.

## Adding a message

1. **Put the files in the media library.** Copy them into the Space under a tidy path, for example
   `audio/<series>/<name>.mp3`, `downloads/audio/<name>.zip`, `video/<name>.mp4`.
   ```bash
   rclone copy ./my-message.mp3 sjmathew:sjmathew-media/audio/my-series/
   ```
2. **Open `/admin/`**, choose **Messages → New Message**, and fill in:
   - Title, date, languages, and Type (Audio, Video or Reading).
   - **Audio parts:** one row per MP3 (part title and file path).
   - **Video:** a YouTube video or playlist id, or the path of an MP4.
   - **Downloads:** button text, file path and a size note such as `49.7 MB`.
   - **Text:** for readings, the article; for audio and video it is optional.
3. **Save.** The site updates when the build finishes. Check the new page, and the message is
   searchable a few minutes later.

Books and tracts: **Books and tracts → New Book or tract**, with the PDF's file path.

## One-time setup for the login

The editor signs in with GitHub. GitHub only issues the sign-in token to a small server that holds a
secret, so a "login helper" is needed. Its code is in `oauth-helper/` (with tests, run
`node --test oauth-helper/handler.test.mjs`).

1. **Create a GitHub OAuth App** (GitHub → Settings → Developer settings → OAuth Apps → New).
   Set the homepage to `https://www.sjmathew.com` and the authorization callback URL to
   `https://<address-of-the-helper>/api/callback`. Note the Client ID and generate a Client secret.
2. **Deploy the helper** anywhere that runs a JavaScript function, with the environment variables
   `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`, and routes `/api/auth` and `/api/callback`.
   Options: a DigitalOcean Function (check its price first; adding one to the site's App Platform
   app may take that app off the free static-site tier), or any other free function host.
3. **Point the editor at it:** in `public/admin/config.yml` set `backend.base_url` to the helper's
   address.
4. **Sign in** at `/admin/` with a GitHub account that has write access to the repository. To let
   someone else edit, add them as a collaborator on the repository.

If you would rather avoid the helper, Sveltia CMS (a drop-in, config-compatible editor) can sign in
with a GitHub personal access token instead. That is a change of editor and needs a decision.

## Trying the editor on your own computer

No login needed. In two terminals:

```bash
npm run dev     # the site, at http://localhost:4321
npm run cms     # a local helper for the editor
```

Then open `http://localhost:4321/admin/index.html` and choose Login. Saves go straight to the files
in your working copy, so you can review them with `git diff` before committing.

## Things to know

- Text changes are safe and reversible: the full history is in GitHub.
- The editor cannot rename or delete media files. Do that in the Space, and update the paths.
- `Old website reference` on each item records where it came from on the old WordPress site. Leave it.
- The Type field decides the layout: Audio shows the player, Video shows the video, Reading shows text.
