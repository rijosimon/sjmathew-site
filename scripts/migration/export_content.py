#!/usr/bin/env python3
"""Turn the WordPress export (public REST API JSON) into the new site's content files.

Inputs : data/raw/posts_all.json, pages.json, cats.json, media-refs.json, media-plan.json
Outputs: src/content/messages/*.md, src/content/library/*.md, src/content/pages/faq.md,
         data/raw/tracks-needed.json (theme audio), data/export-report.md

Rules (Epic 5 of .plan/rebuild.md):
  * Comments, forum, forms, users and draft items are ignored.
  * Posts in the E-book / tract categories become `library` items; everything else becomes a
    `message` of kind audio, video or article.
  * Player playlists (FWD player) become `tracks`; YouTube iframes become `video`;
    links to zips / PDFs / videos become `downloads` (with real file sizes).
  * Presentation-only markup, player scripts and boilerplate are dropped from the body.
"""
import collections
import html as htmllib
import json
import os
import re
import sys
import urllib.parse
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(__file__))
from keys import key_for_theme_audio, slug  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "src", "content")

LANG_BY_CAT = {"Malayalam": "ml", "English": "en", "Hindi": "hi", "Swahili": "sw", "Portuguese": "pt", "Tamil": "ta", "Sinhala": "si"}
LIBRARY_CATS = {5, 6, 10, 14, 17, 21, 22, 25, 27}
TRACT_CATS = {6, 10, 14, 17, 21, 22, 25, 27}
SKIP_PAGE_IDS = {1907: "homepage", 2: "sample page", 1332: "maintenance", 60: "gallery", 1153: "generated list of messages",
                 46: "contact (written by hand)", 38: "about (written by hand)"}
BOILERPLATE = re.compile(r"^(you can use this page to access|these works are copyrighted|if you wish to|click here|download|note:|if you face any difficulty|you can also download)", re.I)
MEDIA_EXT = ("mp3", "zip", "avi", "mp4", "flv", "pdf", "rar", "doc", "docx", "m4a", "wav")


# ---------------------------------------------------------------- helpers
def human(n):
    for unit, div in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= div:
            v = n / div
            return ("%.0f %s" if v >= 100 else "%.1f %s") % (v, unit) if unit != "KB" else "%.0f KB" % v
    return "%d B" % n


def clean_text(s):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def q(v):
    return json.dumps(v, ensure_ascii=False)


def script_lang(text):
    if re.search(r"[ഀ-ൿ]", text): return "ml"
    if re.search(r"[ऀ-ॿ]", text): return "hi"
    if re.search(r"[஀-௿]", text): return "ta"
    if re.search(r"[඀-෿]", text): return "si"
    return None


class Md(HTMLParser):
    """Small HTML -> Markdown converter for article text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.href, self.skip = [], None, 0

    def handle_starttag(self, t, a):
        a = dict(a)
        if t in ("script", "style"): self.skip += 1
        elif t in ("p", "div", "section"): self.out.append("\n\n")
        elif t == "br": self.out.append(" ")
        elif t in ("strong", "b"): self.out.append("**")
        elif t in ("em", "i"): self.out.append("_")
        elif t == "a": self.href = a.get("href"); self.out.append("[")
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"): self.out.append("\n\n## ")
        elif t == "blockquote": self.out.append("\n\n> ")
        elif t == "li": self.out.append("\n- ")
        elif t in ("ul", "ol"): self.out.append("\n")

    def handle_endtag(self, t):
        if t in ("script", "style"): self.skip -= 1
        elif t in ("strong", "b"): self.out.append("**")
        elif t in ("em", "i"): self.out.append("_")
        elif t == "a": self.out.append("](%s)" % (self.href or "#"))
        elif t in ("p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol"): self.out.append("\n\n")

    def handle_data(self, d):
        if not self.skip: self.out.append(d)


def to_markdown(fragment):
    m = Md(); m.feed(fragment)
    t = "".join(m.out)
    t = re.sub(r"\*\*\s*\*\*|_\s*_", "", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n>\s*\n\n([^\n]+)", lambda mm: "\n> " + mm.group(1), t)  # blockquote containing a <p>
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    blocks = []
    for b in re.split(r"\n\s*\n", t):
        plain = re.sub(r"[\s*_>\[\]()#-]+", " ", b).strip()
        if not plain or BOILERPLATE.match(plain) or "videolan" in b.lower() or re.fullmatch(r"(part\s+[ivx\d]+\s*)+", plain, re.I):
            continue
        blocks.append(b.strip())
    return "\n\n".join(blocks)


# ---------------------------------------------------------------- media resolution
class Media:
    def __init__(self):
        plan = json.load(open(os.path.join(RAW, "media-plan.json")))
        self.url_to_key = plan["url_to_key"]
        self.size_by_key = {i["key"]: i["size"] for i in plan["published"]}
        zclass = json.load(open(os.path.join(RAW, "zip-classes.json")))
        self.zip_class = {i["key"]: zclass.get(i["path"], "") for i in plan["published"] if i["ext"] == "zip"}
        self.refs = json.load(open(os.path.join(RAW, "media-refs.json")))
        self.theme = {}          # key -> theme relative path
        self.unresolved = []     # (item, url)

    def key(self, url, ctx=""):
        url = htmllib.unescape(url).strip()
        cand = [url]
        m = re.match(r"https?://[^/]+(/.*)$", url)
        if m:
            cand.append(m.group(1))
        for c in cand:
            for variant in (c, urllib.parse.unquote(c)):
                if variant in self.url_to_key:
                    return self.url_to_key[variant]
        if "/wp-content/themes/goodnews5/" in url:
            rel = urllib.parse.unquote(url.split("/wp-content/themes/goodnews5/")[1])
            k = key_for_theme_audio(rel)
            self.theme[k] = rel
            return k
        if url.split("?")[0].rsplit(".", 1)[-1].lower() in MEDIA_EXT + ("jpg", "jpeg", "png", "gif"):
            self.unresolved.append((ctx, url))
        return None


# ---------------------------------------------------------------- one WP item -> content
def playlists(html):
    out = []
    for ul in re.finditer(r"<ul id='fwdrapPlaylist\d+'[^>]*>(.*?)</ul>", html, re.S):
        for li in re.finditer(r"<li([^>]*)>(.*?)</li>", ul.group(1), re.S):
            attrs = li.group(1)
            m = re.search(r"data-path='([^']+)'", attrs)
            if m:
                out.append((clean_text(li.group(2)) or "Track", m.group(1)))
    return out


def download_table(html):
    """Old video/audio posts list files in <table id='messages'>: header row, then one row per type."""
    rows = []
    for tbl in re.finditer(r"<table[^>]*id=[\"']messages[\"'][^>]*>(.*?)</table>", html, re.S | re.I):
        header = []
        for tr in re.finditer(r"<tr[^>]*>(.*?)</tr>", tbl.group(1), re.S):
            cells = re.findall(r"<(th|td)[^>]*>(.*?)</\1>", tr.group(1), re.S)
            texts = [clean_text(c[1]) for c in cells]
            if not any(re.search(r'href="', c[1]) for c in cells):
                if any(re.search(r"quality|duration", t, re.I) for t in texts):
                    header = texts
                continue
            first = texts[0] if texts else ""
            for idx, (tag, inner) in enumerate(cells):
                for a in re.finditer(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", inner, re.S):
                    col = header[idx] if idx < len(header) else ""
                    rows.append({"url": a.group(1), "type": first, "col": col, "text": clean_text(a.group(2))})
    return rows


def paragraph_label(html, url, atext):
    for p in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.S):
        if url in p.group(1) or htmllib.escape(url) in p.group(1):
            t = clean_text(p.group(1))
            if atext:
                t = t.replace(atext, " ")
            t = re.sub(r"^(if you wish to|if you would like to|you can|to)\s+", "", t.strip(), flags=re.I)
            t = re.sub(r"[,;:.\s]*(please)?[,;:.\s]*$", "", t, flags=re.I).strip()
            if 3 < len(t) < 90:
                return t[0].upper() + t[1:]
    return None


FWDMSP = json.load(open(os.path.join(RAW, "fwdmsp-playlists.json")))


def fwdmsp_playlist(html):
    m = re.search(r"\[fwdmsp[^\]]*playlist_id=[\"\u201d\u201c'\u2032\u2033]*(\d+)", htmllib.unescape(html))
    return FWDMSP.get(m.group(1)) if m else None


def convert(item, kind_hint, media, cats, report):
    h = item["content"]["rendered"]
    cat_ids = item.get("categories", [])
    title = clean_text(item["title"]["rendered"])
    wp_id = item["id"]

    langs = []
    for c in cat_ids:
        name = cats.get(c, {}).get("name", "")
        for key, code in LANG_BY_CAT.items():
            if name.startswith(key) and code not in langs:
                langs.append(code)
    if not langs:
        sl = script_lang(title)
        langs = [sl] if sl else ["en"]
        report["language_inferred"].append((wp_id, title[:40], langs[0]))

    # --- media inside the item
    tracks, cover = [], None
    for ttl, url in playlists(h):
        k = media.key(url, "%s track" % wp_id)
        if k:
            tracks.append({"title": ttl, "src": k})
    pl = fwdmsp_playlist(h)
    if pl and not tracks:
        for tr in pl["tracks"]:
            k = media.key(tr["audio"], "%s track" % wp_id)
            if k:
                tracks.append({"title": tr["name"] or "Track", "src": k})
    seen_src = collections.Counter(t["src"] for t in tracks)
    dup_tracks = [s for s, n in seen_src.items() if n > 1]
    if dup_tracks:
        report["duplicate_track_sources"].append((wp_id, title[:40], len(dup_tracks)))
    m = re.search(r"data-thumb(?:nail-)?path='([^']+)'", h)
    if m:
        cover = media.key(m.group(1), "%s cover" % wp_id)

    videos = []
    for y in dict.fromkeys(re.findall(r"youtube(?:-nocookie)?\.com/embed/(videoseries\?list=[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11})", h)):
        videos.append({"provider": "youtube", "playlist": y.split("list=")[1]} if y.startswith("videoseries") else {"provider": "youtube", "id": y})

    downloads, seen_keys = [], set()

    def add_download(url, label, note=None):
        k = media.key(url, "%s download" % wp_id)
        if not k or k in seen_keys or k.startswith("images/"):
            return
        seen_keys.add(k)
        if k.startswith("video/"):
            return  # played inline, see below
        size = media.size_by_key.get(k)
        entry = {"label": label, "href": k}
        note = note or (human(size) if size else None)
        if note:
            entry["note"] = note
        downloads.append(entry)

    for row in download_table(h):
        kind_word = row["type"].strip() or "File"
        q_word = re.sub(r"\s*quality\s*", "", row["col"], flags=re.I).strip()
        label = kind_word if not q_word else "%s, %s quality" % (kind_word, q_word.lower())
        add_download(row["url"], label)
    for a in re.finditer(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", h, re.S):
        url = htmllib.unescape(a.group(1))
        if url.split("?")[0].rsplit(".", 1)[-1].lower() not in MEDIA_EXT:
            continue
        atext = clean_text(a.group(2))
        label = atext if len(atext) > 12 and not re.match(r"(click here|download)", atext, re.I) else (paragraph_label(h, a.group(1), atext) or atext or "Download")
        label = re.sub(r"\s+[–-]\s+\d+(\.\d+)?\s*[MK]b$", "", label, flags=re.I)  # old "Download – 28 Mb"
        add_download(url, label or "Download")

    # local video files (converted to mp4) -> inline player
    for a in re.finditer(r"(?:href|src)=[\"']([^\"']+\.(?:avi|flv|mp4))[\"']", h, re.I):
        k = media.key(a.group(1), "%s video" % wp_id)
        if k and k.startswith("video/") and not any(v.get("src") == k for v in videos):
            videos.append({"provider": "file", "src": k})

    # --- body text
    stripped = re.sub(r"\[fwdmsp[^\]]*\]", "", h)
    stripped = re.sub(r"<script.*?</script>|<style.*?</style>", "", stripped, flags=re.S | re.I)
    stripped = re.sub(r"<ul id='fwdrap[^']*'.*?</ul>", "", stripped, flags=re.S)
    stripped = re.sub(r"<table[^>]*id=[\"']messages[\"'].*?</table>", "", stripped, flags=re.S | re.I)
    stripped = re.sub(r"<figure[^>]*wp-block-embed.*?</figure>", "", stripped, flags=re.S)
    stripped = re.sub(r"<div class=\"mom_hr[^\"]*\".*?</div>", "", stripped, flags=re.S)
    stripped = re.sub(r"<a[^>]*href=[\"'][^\"']+\.(?:%s)(?:\?[^\"']*)?[\"'][^>]*>.*?</a>" % "|".join(MEDIA_EXT), "", stripped, flags=re.S | re.I)
    body = to_markdown(stripped)

    return {"wp_id": wp_id, "title": title, "date": item["date"][:10], "langs": langs, "tracks": tracks, "cover": cover,
            "videos": videos, "downloads": downloads, "body": body, "cats": cat_ids, "slug": item["slug"]}


def playable_from_zip(c, media, used_keys):
    """Old download-only video posts: the smallest video zip holds one video file. Plan an MP4 of it
    so the page can play it; the zip stays as a download. Returns (zip key, mp4 key) or None."""
    zips = [d["href"] for d in c["downloads"] if d["href"].endswith(".zip") and media.zip_class.get(d["href"]) == "video"]
    if not zips:
        return None
    zips.sort(key=lambda k: media.size_by_key.get(k, 1 << 60))
    zip_key = zips[0]
    mp4 = re.sub(r"(?i)[-_](nq|hq)(?=\.zip$)", "", zip_key)
    mp4 = "video/" + mp4[len("downloads/video/"):-len(".zip")] + ".mp4"
    n, base = 2, mp4
    while mp4 in used_keys:
        mp4 = base[:-4] + "-%d.mp4" % n
        n += 1
    used_keys.add(mp4)
    return zip_key, mp4


def pick_kind(c, is_page):
    if c["tracks"]:
        return "audio"
    if c["videos"]:
        return "video"
    if any(d["href"].startswith("downloads/audio/") for d in c["downloads"]):
        return "audio"
    if any(d["href"].startswith("downloads/video/") for d in c["downloads"]):
        return "video"
    return "article"


def make_slug(c, used):
    latin = re.sub(r"\(([^)]*)\)", r" \1 ", c["title"])
    base = slug(latin, keep_dot=False) if re.search(r"[A-Za-z]{3}", latin) else ""
    if not base or base == "file":
        base = "message-%d" % c["wp_id"]
    base = base[:70].strip("-")
    s = base
    if s in used:
        s = "%s-%d" % (base, c["wp_id"])
    used.add(s)
    return s


def write_md(path, front, body=""):
    lines = ["---"] + ["%s: %s" % (k, v) for k, v in front.items() if v is not None] + ["---", "", body.strip(), ""]
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def rewrite_internal_links(report):
    """Links between old posts (http://www.sjmathew.com/<slug>/) become links to the new pages."""
    where = {}
    for coll in ("messages", "library"):
        d = os.path.join(OUT, coll)
        for f in os.listdir(d):
            if not f.endswith(".md"):
                continue
            text = open(os.path.join(d, f), encoding="utf-8").read()
            m = re.search(r'"wpSlug": "([^"]+)"', text)
            if m:
                where[urllib.parse.unquote(m.group(1)).lower()] = "/%s/%s/" % (coll, f[:-3])
    where["faq"] = "/faq/"
    where["about"] = "/about/"
    where["contact"] = "/contact/"
    pat = re.compile(r"\[([^\]]*)\]\(https?://(?:www\.)?sjmathew\.com/?([^)\s]*)\)")
    fixed = dropped = 0
    for coll in ("messages", "library", "pages"):
        d = os.path.join(OUT, coll)
        for f in os.listdir(d):
            if not f.endswith(".md"):
                continue
            path = os.path.join(d, f)
            text = open(path, encoding="utf-8").read()

            def sub(m):
                nonlocal fixed, dropped
                slug_ = urllib.parse.unquote(m.group(2).strip("/").split("?")[0].split("#")[0]).lower()
                if not slug_:
                    fixed += 1
                    return "[%s](/)" % m.group(1)
                if slug_ in where:
                    fixed += 1
                    return "[%s](%s)" % (m.group(1), where[slug_])
                dropped += 1
                report["dropped_internal_links"].append((f, m.group(0)[:70]))
                return m.group(1)

            new = pat.sub(sub, text)
            if new != text:
                open(path, "w", encoding="utf-8").write(new)
    report["internal_links"] = [(fixed, dropped)]


def main():
    posts = json.load(open(os.path.join(RAW, "posts_all.json")))
    pages = json.load(open(os.path.join(RAW, "pages.json")))
    cats = {c["id"]: c for c in json.load(open(os.path.join(RAW, "cats.json")))}
    media = Media()
    report = collections.defaultdict(list)
    for d in ("messages", "library", "pages"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
        for f in os.listdir(os.path.join(OUT, d)):
            if f.endswith(".md") and f != "about.md":
                os.remove(os.path.join(OUT, d, f))
    used = set()
    video_from_zip, used_video_keys = [], set()
    counts = collections.Counter()

    for src, items in (("post", posts), ("page", pages)):
        for item in items:
            wp_id = item["id"]
            if src == "page" and wp_id in SKIP_PAGE_IDS:
                report["skipped_pages"].append((wp_id, clean_text(item["title"]["rendered"]), SKIP_PAGE_IDS[wp_id]))
                continue
            c = convert(item, src, media, cats, report)
            source = {"wpId": wp_id, "wpSlug": item["slug"], "wpType": src}
            if src == "page" and wp_id == 48:  # FAQ
                write_md(os.path.join(OUT, "pages", "faq.md"), {"title": q(c["title"])}, c["body"])
                counts["page:faq"] += 1
                continue
            if src == "post" and set(c["cats"]) & LIBRARY_CATS:
                files = [d for d in c["downloads"] if d["href"].startswith(("library/", "downloads/"))]
                files.sort(key=lambda d: (not d["href"].endswith(".pdf"),))
                if not files:
                    report["library_without_file"].append((wp_id, c["title"][:50]))
                    counts["library:skipped(no file)"] += 1
                    continue
                s = make_slug(c, used)
                write_md(os.path.join(OUT, "library", s + ".md"), {
                    "title": q(c["title"]), "date": c["date"], "languages": q(c["langs"]),
                    "type": q("tract" if set(c["cats"]) & TRACT_CATS else "book"),
                    "file": q(files[0]["href"]), "source": q(source)})
                counts["library"] += 1
                continue
            kind = pick_kind(c, src == "page")
            if src == "page" and kind == "article" and not c["body"]:
                report["skipped_pages"].append((wp_id, c["title"], "no content"))
                continue
            if kind == "article" and not c["body"] and not c["downloads"]:
                report["empty_posts"].append((wp_id, c["title"][:50]))
                continue
            if kind == "video" and not c["videos"]:
                pz = playable_from_zip(c, media, used_video_keys)
                if pz:
                    c["videos"] = [{"provider": "file", "src": pz[1]}]
                    video_from_zip.append({"zip": pz[0], "key": pz[1], "wpId": wp_id})
                    counts["message:video (played from its zip)"] += 1
            s = make_slug(c, used)
            front = {"title": q(c["title"]), "date": c["date"], "languages": q(c["langs"]), "kind": q(kind)}
            if 33 in c["cats"]:
                front["series"] = q("Malayalam Talk Shows")
            if c["cover"]: front["cover"] = q(c["cover"])
            if c["tracks"]: front["tracks"] = q(c["tracks"])
            if c["videos"]:
                front["video"] = q(c["videos"][0])
                if len(c["videos"]) > 1: front["moreVideos"] = q(c["videos"][1:])
            if c["downloads"]: front["downloads"] = q(c["downloads"])
            front["source"] = q(source)
            write_md(os.path.join(OUT, "messages", s + ".md"), front, c["body"])
            counts["message:" + kind] += 1
            if kind in ("audio", "video") and not c["tracks"] and not c["videos"]:
                counts["message:%s (downloads only)" % kind] += 1

    rewrite_internal_links(report)
    json.dump(video_from_zip, open(os.path.join(RAW, "video-from-zip.json"), "w"), indent=1)

    tracks_theme = sorted(media.theme.items())
    json.dump(tracks_theme, open(os.path.join(RAW, "theme-audio-keys.json"), "w"), indent=1)
    lines = ["# Content export report (Epic 5)", "", "Generated by `scripts/migration/export_content.py`.", "", "## Counts", ""]
    lines += ["- %s: %d" % (k, v) for k, v in sorted(counts.items())]
    lines += ["", "## Needs a human look", ""]
    lines.append("- Language guessed from the title (no language category): %d" % len(report["language_inferred"]))
    lines.append("- Posts whose player lists the same file for several parts: %d" % len(report["duplicate_track_sources"]))
    lines.append("- Library posts with no file we could publish (skipped): %d" % len(report["library_without_file"]))
    lines.append("- Media links that could not be resolved: %d" % len(media.unresolved))
    lines.append("- Empty posts skipped: %d" % len(report["empty_posts"]))
    fixed, dropped = report["internal_links"][0]
    lines.append("- Links between old pages: %d rewritten to new pages, %d pointed at pages that no longer exist (link removed, text kept)" % (fixed, dropped))
    for title, key in (("Skipped pages", "skipped_pages"), ("Library posts without a file", "library_without_file"),
                       ("Unresolved media links", None), ("Same file used for several parts", "duplicate_track_sources"),
                       ("Language inferred from title", "language_inferred")):
        lines += ["", "### " + title, ""]
        rows = media.unresolved if key is None else report[key]
        lines += ["- %s" % (", ".join(map(str, r)) if isinstance(r, (tuple, list)) else r) for r in rows[:60]]
    open(os.path.join(ROOT, "data", "export-report.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[:24]))


if __name__ == "__main__":
    main()
