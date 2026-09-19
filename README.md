# sjmathew.com

A fresh static rebuild of sjmathew.com (recorded messages, e-books and tracts in Malayalam, English, Hindi and Swahili), replacing the old WordPress site.

Status: **design prototype**. Content is a small real sample; audio, video and PDFs are placeholders in `public/sample/`. The banner and `noindex` tag come from `PREVIEW` in `src/lib/site.ts`.

## Decisions

| Topic | Decision |
|---|---|
| Stack | Astro 7, static output, no server code |
| Hosting | DigitalOcean: App Platform static site + Spaces for media (about $5/month) |
| Comments / contact form | None. Contact is a static page |
| URLs | New structure; old slugs are not preserved |
| Media | Everything kept, deduplicated and converted to web formats (later epics) |
| Editing | Decap CMS, Git-backed (later epic) |
| Languages | Malayalam, English, Hindi, Swahili; fonts are Noto Serif/Sans per script |

The working plan lives in `.plan/rebuild.md` (gitignored).

## Run it

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # static site in dist/
npm run check    # type-check .astro and TypeScript files
```

Needs Node 22.12+ and internet access at build time (the fonts are fetched from Fontsource and self-hosted in the output).

## Layout

- `src/content/messages/`: audio, video and reading entries (Markdown + front matter, schema in `src/content.config.ts`)
- `src/content/library/`: e-books and tracts
- `src/content/pages/`: About
- `src/components/`: cards, filters, `AudioPlayer`, `VideoPlayer` (YouTube click-to-load or a self-hosted file)
- `src/pages/`: routes (`/`, `/messages/`, `/messages/[slug]/`, `/series/`, `/library/`, `/about/`, `/contact/`)
- `src/styles/global.css`: design tokens (light/dark palette, type scale, per-script line heights)
