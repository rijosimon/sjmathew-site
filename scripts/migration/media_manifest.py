#!/usr/bin/env python3
"""Turn the raw `find` listing of the old media volume into a manifest and pick the
files worth hashing for duplicate detection.

Input : data/raw/media-files.nul   (size TAB mtime TAB relative-path, NUL-separated)
Output: data/raw/media-manifest.tsv  (path, size, mtime, top folder, extension)
        data/raw/hash-candidates.nul (paths whose size equals another file's size)
"""
import collections, os, sys

RAW = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")

def load():
    text = open(os.path.join(RAW, "media-files.nul"), "rb").read().decode("utf-8", "surrogateescape")
    rows = []
    for rec in filter(None, text.split("\0")):
        size, mtime, path = rec.split("\t", 2)
        rows.append((path, int(size), float(mtime)))
    return rows

def ext_of(path):
    base = os.path.basename(path)
    return base.rsplit(".", 1)[-1].lower() if "." in base else "(none)"

def main():
    rows = load()
    with open(os.path.join(RAW, "media-manifest.tsv"), "w", encoding="utf-8") as out:
        out.write("path\tsize\tmtime\ttop\text\n")
        for path, size, mtime in rows:
            parts = path.split("/")
            top = "/".join(parts[:3]) if parts[0] == "sjmathew" and len(parts) > 2 and parts[1] == "works" else "/".join(parts[:2])
            out.write("%s\t%d\t%d\t%s\t%s\n" % (path, size, mtime, top, ext_of(path)))
    by_size = collections.defaultdict(list)
    for path, size, _ in rows:
        by_size[size].append(path)
    cand = [p for size, ps in by_size.items() if len(ps) > 1 and size > 0 for p in ps]
    with open(os.path.join(RAW, "hash-candidates.nul"), "wb") as f:
        for p in sorted(cand):
            f.write(p.encode("utf-8", "surrogateescape") + b"\0")
    sizes = dict((p, s) for p, s, _ in rows)
    print("files: %d  total: %.1f GB" % (len(rows), sum(sizes.values()) / 1e9))
    print("hash candidates (same size as another file): %d files, %.1f GB" % (len(cand), sum(sizes[p] for p in cand) / 1e9))
    empty = [p for p, s, _ in rows if s == 0]
    print("zero-byte files: %d" % len(empty))
    exts = collections.Counter(); esize = collections.Counter()
    for p, s, _ in rows:
        e = ext_of(p); exts[e] += 1; esize[e] += s
    print("by extension (files, GB):")
    for e, sz in esize.most_common(14):
        print("  %-8s %6d  %8.2f" % (e, exts[e], sz / 1e9))

if __name__ == "__main__":
    main()
