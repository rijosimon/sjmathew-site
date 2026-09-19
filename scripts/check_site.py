#!/usr/bin/env python3
"""Check the built site (dist/) for broken internal links and missing media.

  python3 scripts/check_site.py [--media DIR]

* Every internal href/src (pages, assets, feeds) must exist in dist/.
* Every /media/... URL must exist in the processed media library (default ~/Workspace/sjmathew-media/out).
Exit status is 1 if anything is broken.
"""
import argparse
import collections
import html
import os
import re
import sys
import urllib.parse

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIST = os.path.join(ROOT, "dist")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", default=os.path.expanduser("~/Workspace/sjmathew-media/out"))
    args = ap.parse_args()
    pages = []
    for base, _, files in os.walk(DIST):
        for f in files:
            if f.endswith(".html") and "pagefind" not in base:
                pages.append(os.path.join(base, f))
    broken = collections.defaultdict(set)
    media_used, media_missing = set(), collections.defaultdict(set)
    attr = re.compile(r"""(?:href|src|data-src|poster)=["']([^"']+)["']""")
    tracks = re.compile(r'data-tracks="([^"]+)"')
    for page in pages:
        rel = "/" + os.path.relpath(page, DIST).replace("index.html", "")
        text = open(page, encoding="utf-8").read()
        urls = [html.unescape(u) for u in attr.findall(text)]
        for t in tracks.findall(text):  # player track lists are JSON inside an attribute
            urls += re.findall(r'"src":"([^"]+)"', html.unescape(t))
        for u in urls:
            if not u or u.startswith(("#", "mailto:", "tel:", "data:", "javascript:")) or re.match(r"^(https?:)?//", u):
                continue
            path = urllib.parse.unquote(u.split("#")[0].split("?")[0])
            if path.startswith("/media/"):
                key = path[len("/media/"):]
                media_used.add(key)
                if not os.path.exists(os.path.join(args.media, key)):
                    media_missing[key].add(rel)
                continue
            if not path.startswith("/"):
                path = os.path.normpath(os.path.join(os.path.dirname(rel), path))
            target = os.path.join(DIST, path.lstrip("/"))
            if not (os.path.exists(target) or os.path.exists(os.path.join(target, "index.html"))):
                broken[path].add(rel)
    print("pages checked: %d | distinct media files referenced: %d" % (len(pages), len(media_used)))
    print("broken internal links: %d" % len(broken))
    for p, where in sorted(broken.items())[:15]:
        print("   %s   (on %s%s)" % (p, sorted(where)[0], " +%d more" % (len(where) - 1) if len(where) > 1 else ""))
    print("media files referenced but missing: %d" % len(media_missing))
    for k, where in sorted(media_missing.items())[:15]:
        print("   %s   (on %s%s)" % (k, sorted(where)[0], " +%d more" % (len(where) - 1) if len(where) > 1 else ""))
    return 1 if broken or media_missing else 0


if __name__ == "__main__":
    sys.exit(main())
