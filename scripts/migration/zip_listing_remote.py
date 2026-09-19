# Runs on the OLD server (Python 3.5, no f-strings). Reads NUL-separated zip paths
# (relative to /mnt/volume-sgp1-01/uploads) on stdin and prints one JSON object per zip
# with its members, sizes and CRC32. Only the zip central directory is read.
import json, sys, zipfile
base = "/mnt/volume-sgp1-01/uploads/"
data = sys.stdin.buffer.read().decode("utf-8", "surrogateescape").split("\0")
for rel in [d for d in data if d]:
    rec = {"path": rel}
    try:
        with zipfile.ZipFile(base + rel) as z:
            rec["members"] = [[i.filename, i.file_size, i.compress_size, i.CRC, 1 if i.filename.endswith("/") else 0] for i in z.infolist()]
    except Exception as e:
        rec["error"] = str(e)[:200]
    sys.stdout.write(json.dumps(rec, ensure_ascii=True) + "\n")
