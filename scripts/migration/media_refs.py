#!/usr/bin/env python3
"""Find every media file the published WordPress posts/pages point at, and map each
URL to a path on the old media volume (or the theme folder).

Inputs : data/raw/posts_all.json, pages.json (public WP REST API export),
         data/raw/media-manifest.tsv
Output : data/raw/media-refs.json  {url: {"kind":..., "volume_path":..., "exists":...}}
"""
import html as htmllib, json, os, re, sys, urllib.parse

RAW = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
MEDIA_EXT = r"(?:mp3|zip|avi|mp4|flv|pdf|rar|doc|docx|m4a|wav|ppt|pptx|jpg|jpeg|png|gif)"

def load_manifest():
    man = {}
    for line in open(os.path.join(RAW, "media-manifest.tsv"), encoding="utf-8").read().split("\n")[1:]:
        if line:
            path, size, *_ = line.split("\t")
            man[path] = int(size)
    return man

def urls_in(html):
    """URLs (spaces allowed, HTML entities decoded) that end in a media extension."""
    html = htmllib.unescape(html)
    found = set()
    pat = r"""["'(=]\s*((?:https?://[^/\s"'()<>]+(?:/websites/sjmathew-wp)?)?/[^"'()<>]+?\.""" + MEDIA_EXT + r""")(?:\?[^"'()<>]*)?["')<]"""
    for m in re.finditer(pat, html, re.I):
        found.add(m.group(1).strip())
    return found

def to_volume_path(url):
    p = urllib.parse.unquote(re.sub(r"^https?://[^/]+", "", url))
    p = re.sub(r"/{2,}", "/", p)
    p = re.sub(r"^/websites/sjmathew-wp", "", p)
    if p.startswith("/wp-content/uploads/"):
        return "sjmathew/" + p[len("/wp-content/uploads/"):]
    return None

def main():
    man = load_manifest()
    docs = []
    for name in ("posts_all.json", "pages.json"):
        for item in json.load(open(os.path.join(RAW, name))):
            docs.append((name.split("_")[0].split(".")[0], item))
    refs = {}
    for kind, item in docs:
        for u in urls_in(item["content"]["rendered"]):
            r = refs.setdefault(u, {"used_by": []})
            r["used_by"].append("%s:%s" % (kind, item["id"]))
    # tracks of the second player plugin: playlists live in the database, posts only carry an id
    playlists = json.load(open(os.path.join(RAW, "fwdmsp-playlists.json")))
    for kind, item in docs:
        m = re.search(r"\[fwdmsp[^\]]*playlist_id=[\"\u201d\u201c'\u2032\u2033]*(\d+)", htmllib.unescape(item["content"]["rendered"]))
        if m and m.group(1) in playlists:
            for track in playlists[m.group(1)]["tracks"]:
                if track["audio"]:
                    refs.setdefault(track["audio"], {"used_by": []})["used_by"].append("%s:%s" % (kind, item["id"]))
    for u, r in refs.items():
        vp = to_volume_path(u)
        r["volume_path"] = vp
        r["in_theme"] = "/themes/" in u
        r["exists"] = bool(vp and vp in man)
        r["size"] = man.get(vp, 0)
    json.dump(refs, open(os.path.join(RAW, "media-refs.json"), "w"), indent=1)
    on_vol = [r for r in refs.values() if r["volume_path"]]
    print("distinct media URLs referenced: %d | on the volume path: %d | exist on volume: %d | theme: %d | other/external: %d" % (
        len(refs), len(on_vol), sum(r["exists"] for r in on_vol), sum(r["in_theme"] for r in refs.values()),
        sum(1 for r in refs.values() if not r["volume_path"] and not r["in_theme"])))
    missing = [u for u, r in refs.items() if r["volume_path"] and not r["exists"]]
    print("referenced but MISSING from the volume: %d" % len(missing))
    for u in missing[:8]: print("   ", u)

if __name__ == "__main__":
    main()
