#!/usr/bin/env python3
"""Decide exactly which media files to carry over, and under which new keys.

Policy (see .plan/rebuild.md, Epic 3):
  * A file is PUBLISHED if a published post or page links to it (directly or through a
    player playlist). Broken links are repaired by name matching where the file exists
    under a slightly different name (e.g. Class_8.zip -> Class_08.zip).
  * Exact duplicates (same md5, or same size when that size is unique) are stored once;
    every old path/URL points at the one canonical copy.
  * Zips that are not media (theme/plugin bundles), design sources (PSD/InDesign) and
    broken zips are reported and skipped.
  * Everything else on the volume is ORPHANED: listed in the report, not published.

Inputs : data/raw/media-manifest.tsv, hashes.md5, zip-members.jsonl, zip-classes.json, media-refs.json
Outputs: data/raw/media-plan.json, data/raw/transfer-files.nul, data/media-report.md
"""
import collections
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from keys import key_for_volume_path  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RAW = os.path.join(ROOT, "data", "raw")
GB = 1e9


def norm(name: str) -> str:
    name = urllib.parse.unquote(name).replace("&amp;", "&").lower().replace("&", "and")
    name = re.sub(r"(?<!\d)0+(?=\d)", "", name)  # Class_08 == Class_8
    return re.sub(r"[^a-z0-9.]+", "", name)


def main():
    man = {}
    for line in open(os.path.join(RAW, "media-manifest.tsv"), encoding="utf-8").read().split("\n")[1:]:
        if line:
            p, size, mtime, top, ext = line.split("\t")
            man[p] = {"size": int(size), "top": top, "ext": ext}
    md5 = {}
    for line in open(os.path.join(RAW, "hashes.md5"), encoding="utf-8", errors="surrogateescape"):
        line = line.rstrip("\n")
        if len(line) > 34 and line[32:34] == "  ":
            md5[line[34:]] = line[:32]
    zclass = json.load(open(os.path.join(RAW, "zip-classes.json")))
    refs = json.load(open(os.path.join(RAW, "media-refs.json")))

    # -- resolve references to volume paths
    index_folder = collections.defaultdict(list)
    index_any = collections.defaultdict(list)
    for p in man:
        folder, _, base = p.rpartition("/")
        index_folder[(folder, norm(base))].append(p)
        index_any[norm(base)].append(p)
    resolved, unresolved = {}, []
    for url, r in refs.items():
        if r["in_theme"] or not r["volume_path"]:
            continue
        vp = urllib.parse.unquote(r["volume_path"]).replace("&amp;", "&")
        if vp in man:
            resolved[url] = vp
            continue
        folder, _, base = vp.rpartition("/")
        hit = index_folder.get((folder, norm(base))) or index_any.get(norm(base))
        if hit and len(hit) == 1:
            resolved[url] = hit[0]
        else:
            unresolved.append(url)

    # -- duplicate groups
    groups = collections.defaultdict(list)
    size_count = collections.Counter(v["size"] for v in man.values())
    for p, v in man.items():
        if p in md5:
            gid = md5[p]
        else:
            gid = "size:%d:%s" % (v["size"], p) if size_count[v["size"]] > 1 else "size:%d" % v["size"]
        groups[gid].append(p)
    referenced_paths = set(resolved.values())

    def canonical(paths):
        return sorted(paths, key=lambda p: (p not in referenced_paths, "ftp.sajumathew.net" in p, "/temp/" in p, len(p), p))[0]

    canon = {}
    for gid, paths in groups.items():
        c = canonical(paths)
        for p in paths:
            canon[p] = c

    # -- published set
    skipped = []
    published = {}  # canonical path -> item
    for url, vp in resolved.items():
        c = canon[vp]
        ext = man[c]["ext"]
        if ext == "zip":
            klass = zclass.get(c, "unknown")
            if not (klass.startswith("audio") or klass == "video" or klass == "documents"):
                skipped.append({"path": c, "why": "zip is %s" % klass, "size": man[c]["size"]})
                continue
        if ext in ("rar", "html", "css", "ico"):
            skipped.append({"path": c, "why": "not web media (%s)" % ext, "size": man[c]["size"]})
            continue
        action = "convert-video" if ext in ("avi", "flv", "wmv", "mpg") else "copy"
        published.setdefault(c, {"path": c, "size": man[c]["size"], "ext": ext, "action": action,
                                 "key": key_for_volume_path(c), "md5": md5.get(c), "urls": []})["urls"].append(url)

    # -- key collisions (different files, same slug) get a numeric suffix
    seen = {}
    for c in sorted(published):
        k = published[c]["key"]
        if k in seen and seen[k] != c:
            stem, dot, ext = k.rpartition(".")
            n = 2
            while "%s-%d.%s" % (stem, n, ext) in seen:
                n += 1
            published[c]["key"] = "%s-%d.%s" % (stem, n, ext)
        seen[published[c]["key"]] = c

    url_to_key = {}
    for url, vp in resolved.items():
        c = canon[vp]
        if c in published:
            url_to_key[url] = published[c]["key"]
    dup_url_to_key = {}
    for p, c in canon.items():
        if p != c and c in published:
            dup_url_to_key[p] = published[c]["key"]

    orphans = [p for p in man if canon[p] not in published and canon[p] not in {s["path"] for s in skipped} and p not in referenced_paths]
    orphan_unique = {}
    for p in orphans:
        if canon[p] == p:
            orphan_unique[p] = man[p]

    plan = {"published": sorted(published.values(), key=lambda i: i["key"]), "url_to_key": url_to_key,
            "path_to_key": dup_url_to_key, "unresolved_urls": unresolved, "skipped": skipped}
    json.dump(plan, open(os.path.join(RAW, "media-plan.json"), "w"), indent=1)
    with open(os.path.join(RAW, "transfer-files.nul"), "wb") as f:
        for it in plan["published"]:
            f.write(it["path"].encode("utf-8", "surrogateescape") + b"\0")

    # -- report
    total = sum(v["size"] for v in man.values())
    dup_bytes = sum(man[p]["size"] for p, c in canon.items() if p != c)
    pub_bytes = sum(i["size"] for i in plan["published"])
    ref_bytes_with_dups = sum(man[vp]["size"] for vp in set(resolved.values()))
    by_ext = collections.defaultdict(lambda: [0, 0])
    for i in plan["published"]:
        by_ext[i["ext"]][0] += 1
        by_ext[i["ext"]][1] += i["size"]
    orphan_by = collections.defaultdict(lambda: [0, 0])
    for p, v in orphan_unique.items():
        k = v["ext"] if v["ext"] in ("zip", "mp3", "avi", "pdf", "rar", "flv", "mp4") else "images/other"
        orphan_by[k][0] += 1
        orphan_by[k][1] += v["size"]
    lines = ["# Media inventory (Epic 3)", "",
             "Generated by `scripts/migration/build_media_plan.py` from a read-only scan of the old volume on 2026-09-19.", "",
             "## Summary", "",
             "| | Files | GB |", "|---|---:|---:|",
             "| On the volume | %d | %.1f |" % (len(man), total / GB),
             "| Exact duplicates of another file | %d | %.1f |" % (sum(1 for p, c in canon.items() if p != c), dup_bytes / GB),
             "| Linked from published posts/pages (after repairing names) | %d | %.1f |" % (len(set(resolved.values())), ref_bytes_with_dups / GB),
             "| **To publish (linked, deduplicated)** | **%d** | **%.1f** |" % (len(plan["published"]), pub_bytes / GB),
             "| Not published: orphaned (no page links to it), unique | %d | %.1f |" % (len(orphan_unique), sum(v["size"] for v in orphan_unique.values()) / GB),
             "| Not published: software, design sources, broken zips | %d | %.1f |" % (len(skipped), sum(s["size"] for s in skipped) / GB),
             "", "## To publish, by type", "", "| Type | Files | GB |", "|---|---:|---:|"]
    for e, (n, b) in sorted(by_ext.items(), key=lambda x: -x[1][1]):
        lines.append("| %s | %d | %.2f |" % (e, n, b / GB))
    lines += ["", "## Links repaired by name matching", "",
              "%d links pointed at names that do not exist but matched exactly one existing file." % (len(resolved) - sum(1 for u, vp in resolved.items() if urllib.parse.unquote(refs[u]["volume_path"]).replace("&amp;", "&") in man)), "",
              "## Broken links with no matching file (%d)" % len(unresolved), ""] + ["- `%s`" % u for u in unresolved] + [
              "", "## Orphaned unique files (not linked from any page), by type", "", "| Type | Files | GB |", "|---|---:|---:|"]
    for e, (n, b) in sorted(orphan_by.items(), key=lambda x: -x[1][1]):
        lines.append("| %s | %d | %.2f |" % (e, n, b / GB))
    lines += ["", "Largest orphaned files:", ""]
    for p, v in sorted(orphan_unique.items(), key=lambda x: -x[1]["size"])[:15]:
        lines.append("- %.2f GB  `%s`" % (v["size"] / GB, p))
    lines += ["", "## Skipped (not web media)", ""] + ["- %.2f GB  `%s`: %s" % (s["size"] / GB, s["path"], s["why"]) for s in skipped[:30]]
    open(os.path.join(ROOT, "data", "media-report.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[:22]))
    print("...\nfull report: data/media-report.md; plan: data/raw/media-plan.json (%d items, %.1f GB to transfer)" % (len(plan["published"]), pub_bytes / GB))


if __name__ == "__main__":
    main()
