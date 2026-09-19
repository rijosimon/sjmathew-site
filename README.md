# sjmathew.com

A static rebuild of sjmathew.com: recorded messages, e-books and tracts by Saju John Mathew, in Malayalam,
English, Hindi, Swahili, Tamil, Portuguese and Sinhala. It replaces the old WordPress site.

Status: **preview.** The real content and media are imported. The banner and `noindex` tag come from
`PREVIEW` in `src/lib/site.ts`; switch it off when the site goes live.

## How it is built

| Topic | Choice |
|---|---|
| Stack | Astro 7, static output, no server code |
| Hosting | DigitalOcean App Platform (static site); media in a DigitalOcean Space |
| Editing | Decap CMS at `/admin/`, saving commits to this repository (see `docs/EDITING.md`) |
| Search | Pagefind, built after the site (`/search/`) |
| Fonts | Noto Serif and Noto Sans per script, self-hosted at build time |
| Comments, contact form | None; the contact page is plain text |

## Run it

```bash
npm install
npm run dev       # http://localhost:4321  (serves ~/Workspace/sjmathew-media/out at /media if present)
npm run build     # static site in dist/, then the search index
npm run preview   # serve the built site
npm run check     # type-check
npm run cms       # local helper for the editor (no login needed on your own computer)
python3 scripts/check_site.py   # after a build: broken links and missing media
```

Needs Node 22.12+ and internet access at build time (fonts). Media addresses come from
`PUBLIC_MEDIA_BASE_URL` (default `/media`).

## Where things are

- `src/content/messages/`, `library/`, `pages/`: the content (Markdown with front matter; schema in `src/content.config.ts`). File references are media keys such as `audio/ykt/class-08.mp3`.
- `src/components/`, `src/pages/`, `src/styles/global.css`: the design, players, filters, search and feed.
- `public/admin/`: the editor. `oauth-helper/`: its GitHub login helper (tested, not deployed).
- `docs/EDITING.md`: adding messages and setting up the editor login. `docs/MEDIA.md`: the media library and how to upload it.
- `scripts/migration/`: the tools that read the old site and produced the content and media library. `data/media-report.md` and `data/export-report.md` say what they found.
- `.do/app.yaml`: the App Platform app definition.
