#!/usr/bin/env python3
"""Build the publishable media library (`out/`) from the files copied off the old volume.

  raw/   files as they were on the old server (relative paths kept)
  out/   the same files under their NEW keys, ready to upload:
           - copies (hard links, no extra disk) for zips, mp3, pdf, images
           - AVI/FLV converted to H.264/AAC MP4 (max 1280 wide, capped at ~1.5 Mbit/s, web-optimised)
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
import tempfile
import zipfile

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


def _encode(src, tmp, video_args):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
           "-vf", "scale='min(1280,iw)':-2:flags=lanczos,format=yuv420p", *video_args,
           "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-movflags", "+faststart", tmp]
    return subprocess.run(cmd, capture_output=True, text=True)


def convert_video(src, dst):
    """AVI/FLV/... -> web-ready MP4. Uses the Mac's hardware H.264 encoder (fast, ~1.4 Mbit/s target);
    falls back to x264 with a capped bitrate if the hardware encoder refuses a file."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part.mp4"
    attempts = [
        ["-c:v", "h264_videotoolbox", "-b:v", "1400k", "-maxrate", "2000k", "-profile:v", "high", "-allow_sw", "1"],
        ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-maxrate", "1500k", "-bufsize", "3000k"],
    ]
    err = ""
    for args in attempts:
        r = _encode(src, tmp, args)
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, dst)
            return None
        err = (r.stderr or "")[-200:]
        if os.path.exists(tmp):
            os.remove(tmp)
    return "ffmpeg failed: " + err


VIDEO_EXT = (".avi", ".flv", ".mp4", ".wmv", ".mpg", ".mpeg", ".mov", ".m4v")


def video_from_zip(zip_src, dst):
    """Take the largest video file out of a zip and convert it. Returns an error string or None."""
    with tempfile.TemporaryDirectory(dir=BASE) as tmp:
        try:
            with zipfile.ZipFile(zip_src) as z:
                members = [i for i in z.infolist() if i.filename.lower().endswith(VIDEO_EXT) and not i.is_dir()]
                if not members:
                    return "no video file in zip"
                best = max(members, key=lambda i: i.file_size)
                extracted = z.extract(best, tmp)
        except (zipfile.BadZipFile, OSError) as e:
            return "cannot read zip: %s" % e
        return convert_video(extracted, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", action="store_true", help="also convert videos (slow)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    plan = json.load(open(os.path.join(RAW, "media-plan.json")))
    mapfile = os.path.join(ROOT, "data", "media-map.json")
    media_map = json.load(open(mapfile)) if os.path.exists(mapfile) else {}
    todo, waiting, failed, adopt = [], [], [], []

    for it in plan["published"]:
        src = os.path.join(SRC, it["path"])
        dst = os.path.join(OUT, it["key"])
        if os.path.exists(dst) and it["key"] in media_map:
            continue
        if os.path.exists(dst) and it["action"] == "convert-video" and os.path.getsize(dst) > 0:
            adopt.append((it["key"], dst, it["ext"], it["path"]))
            continue
        if not os.path.exists(src) or os.path.getsize(src) != it["size"]:
            waiting.append(it["path"])
            continue
        if it["action"] == "convert-video" and not args.videos:
            continue
        todo.append((it, src, dst))

    # videos taken out of their zips (old download-only posts)
    zip_jobs = []
    vfz = os.path.join(RAW, "video-from-zip.json")
    if args.videos and os.path.exists(vfz):
        by_key = {i["key"]: i for i in plan["published"]}
        for job in json.load(open(vfz)):
            it = by_key.get(job["zip"])
            dst = os.path.join(OUT, job["key"])
            if not it or (os.path.exists(dst) and job["key"] in media_map):
                continue
            if os.path.exists(dst) and os.path.getsize(dst) > 0:
                adopt.append((job["key"], dst, "mp4", job["zip"] + " (video inside)"))
                continue
            src = os.path.join(SRC, it["path"])
            if os.path.exists(src) and os.path.getsize(src) == it["size"]:
                zip_jobs.append((job, src, dst))
            else:
                waiting.append(it["path"])

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

    for key, dst, typ, source in adopt:
        media_map[key] = {"size": os.path.getsize(dst), "md5": md5(dst), "type": typ if typ != "avi" else "mp4", "source": source}
    if adopt:
        print("adopted %d finished conversions" % len(adopt), flush=True)

    def work(job):
        it, src, dst = job
        if it.get("zip_job"):
            return it, video_from_zip(src, dst)
        if it["action"] == "convert-video":
            return it, convert_video(src, dst)
        link_or_copy(src, dst)
        return it, None

    jobs = [({"zip_job": True, "key": j["key"], "path": j["zip"], "ext": "mp4", "action": "convert-video", "zip": j["zip"]}, src, dst) for j, src, dst in zip_jobs] + todo
    workers = 3 if args.videos else 8
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for n, (it, err) in enumerate(ex.map(work, jobs), 1):
            if err:
                failed.append((it["path"], err))
                continue
            dst = os.path.join(OUT, it["key"])
            source = it["zip"] + " (video inside)" if it.get("zip_job") else it["path"]
            media_map[it["key"]] = {"size": os.path.getsize(dst), "md5": md5(dst), "type": it["ext"] if it["action"] == "copy" else "mp4", "source": source}
            if n % 5 == 0:
                print("  %d/%d" % (n, len(jobs)), flush=True)
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
