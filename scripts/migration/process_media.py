#!/usr/bin/env python3
"""Build the publishable media library (`out/`) from the files copied off the old volume.

  raw/   files as they were on the old server (relative paths kept)
  out/   the same files under their NEW keys, ready to upload:
           - copies (hard links, no extra disk) for zips, mp3, pdf, images
           - AVI/FLV converted to H.264/AAC MP4 (max 720p, web-optimised)
           - theme-folder MP3s taken from the site-files backup

Only files whose size on disk equals the size on the old server are used, so a transfer that is
still running or was interrupted is never mistaken for a finished file.

Usage: process_media.py [--videos] [--limit N]
Writes data/media-map.json (key -> size, md5, type, source) for every file in out/.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RAW = os.path.join(ROOT, "data", "raw")
BASE = os.path.expanduser("~/Workspace/sjmathew-media")
SRC = os.path.join(BASE, "raw")
THEME = os.path.join(BASE, "raw-theme", "html", "wp-content", "themes", "goodnews5")
OUT = os.path.join(BASE, "out")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def link_or_copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def convert_video(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
           "-vf", "scale='min(1280,iw)':-2:flags=lanczos,format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-crf", "25",
           "-c:a", "aac", "-b:a", "96k", "-ac", "2",
           "-movflags", "+faststart", tmp]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
        if os.path.exists(tmp):
            os.remove(tmp)
        return "ffmpeg failed: " + (r.stderr or "")[-200:]
    os.replace(tmp, dst)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", action="store_true", help="also convert videos (slow)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    plan = json.load(open(os.path.join(RAW, "media-plan.json")))
    mapfile = os.path.join(ROOT, "data", "media-map.json")
    media_map = json.load(open(mapfile)) if os.path.exists(mapfile) else {}
    todo, waiting, failed = [], [], []

    for it in plan["published"]:
        src = os.path.join(SRC, it["path"])
        dst = os.path.join(OUT, it["key"])
        if os.path.exists(dst) and it["key"] in media_map:
            continue
        if not os.path.exists(src) or os.path.getsize(src) != it["size"]:
            waiting.append(it["path"])
            continue
        if it["action"] == "convert-video" and not args.videos:
            continue
        todo.append((it, src, dst))

    # theme-folder audio (from the backup, not from the volume)
    theme = json.load(open(os.path.join(RAW, "theme-audio-keys.json")))
    for key, rel in theme:
        src, dst = os.path.join(THEME, rel), os.path.join(OUT, key)
        if os.path.exists(src) and not (os.path.exists(dst) and key in media_map):
            todo.append(({"key": key, "path": "themes/goodnews5/" + rel, "size": os.path.getsize(src), "action": "copy", "ext": "mp3"}, src, dst))
        elif not os.path.exists(src):
            failed.append(("missing theme file", rel))

    if args.limit:
        todo = todo[: args.limit]
    print("to process: %d | waiting for transfer: %d | already done: %d" % (len(todo), len(waiting), len(media_map)))

    def work(job):
        it, src, dst = job
        if it["action"] == "convert-video":
            err = convert_video(src, dst)
            if err:
                return it, err
        else:
            link_or_copy(src, dst)
        return it, None

    workers = 3 if args.videos else 8
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for n, (it, err) in enumerate(ex.map(work, todo), 1):
            if err:
                failed.append((it["path"], err))
                continue
            dst = os.path.join(OUT, it["key"])
            media_map[it["key"]] = {"size": os.path.getsize(dst), "md5": md5(dst), "type": it["ext"] if it["action"] == "copy" else "mp4",
                                    "source": it["path"]}
            if n % 25 == 0:
                print("  %d/%d" % (n, len(todo)), flush=True)
                json.dump(media_map, open(mapfile, "w"), indent=0, sort_keys=True)
    json.dump(media_map, open(mapfile, "w"), indent=0, sort_keys=True)
    total = sum(v["size"] for v in media_map.values())
    print("media-map.json: %d files, %.1f GB" % (len(media_map), total / 1e9))
    if failed:
        print("FAILED (%d):" % len(failed))
        for f in failed[:20]:
            print("  ", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
