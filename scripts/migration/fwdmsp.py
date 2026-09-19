#!/usr/bin/env python3
"""Recover the audio playlists of the second FWD player plugin (`[fwdmsp playlist_id="N"]`).

Those playlists are not in the post text: they live in one serialized PHP option
(`fwdmsp_data`) in wp_options. This reads the database dump in the archive, unserializes that
option and writes data/raw/fwdmsp-playlists.json: {playlist id: {"name", "tracks": [{"name","audio"}]}}.
"""
import gzip
import json
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DUMP = os.path.expanduser("~/Workspace/sjmathew-archive/2026-09-19/wordpress.sql.gz")
OUT = os.path.join(ROOT, "data", "raw", "fwdmsp-playlists.json")

SQL_ESC = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "Z": "\x1a"}


def sql_unescape(s: str) -> str:
    return re.sub(r"\\(.)", lambda m: SQL_ESC.get(m.group(1), m.group(1)), s, flags=re.S)


def php_unserialize(b: bytes):
    pos = 0

    def parse():
        nonlocal pos
        t = b[pos:pos + 1]
        if t == b"N":
            pos += 2
            return None
        if t in (b"b", b"i", b"d"):
            end = b.index(b";", pos)
            raw = b[pos + 2:end]
            pos = end + 1
            return float(raw) if t == b"d" else int(raw)
        if t == b"s":
            colon = b.index(b":", pos + 2)
            n = int(b[pos + 2:colon])
            start = colon + 2
            s = b[start:start + n]
            pos = start + n + 2
            return s.decode("utf-8", "replace")
        if t in (b"a", b"O"):
            if t == b"O":
                colon = b.index(b":", pos + 2)
                n = int(b[pos + 2:colon])
                pos = colon + 2 + n + 2          # skip O:len:"Class":
            else:
                pos += 2
            colon = b.index(b":", pos)
            count = int(b[pos:colon])
            pos = colon + 2                      # skip :{
            out = {}
            for _ in range(count):
                k = parse()
                out[k] = parse()
            pos += 1                             # skip }
            return out
        raise ValueError("unexpected byte %r at %d" % (t, pos))

    return parse()


def main():
    sql = gzip.open(DUMP, "rt", encoding="utf-8", errors="replace").read()
    m = re.search(r"\(\d+,'fwdmsp_data','((?:[^'\\]|\\.)*)','(?:yes|no)'\)", sql, re.S)
    if not m:
        raise SystemExit("fwdmsp_data option not found in the dump")
    data = php_unserialize(sql_unescape(m.group(1)).encode("utf-8"))
    lists = data["main_playlists_ar"]
    out = {}
    for _, pl in lists.items():
        tracks = []
        for sub in pl.get("playlists", {}).values():
            for tr in sub.get("tracks", {}).values():
                tracks.append({"name": tr.get("name", ""), "audio": tr.get("audio", "")})
        out[str(pl["id"])] = {"name": pl.get("name", ""), "tracks": tracks}
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    n = sum(len(v["tracks"]) for v in out.values())
    print("playlists: %d, tracks: %d -> %s" % (len(out), n, os.path.relpath(OUT, ROOT)))
    for k in list(out)[:3]:
        print("  %s %s: %d tracks, e.g. %s" % (k, out[k]["name"][:40], len(out[k]["tracks"]), (out[k]["tracks"] or [{}])[0]))


if __name__ == "__main__":
    main()
