"""Naming rules for the new media library.

Every published file gets a stable, URL-safe key (its path inside the media bucket).
Keys are derived from the old location, so the mapping is reproducible.

  audio/<folder...>/<file>.mp3              playable audio (loose files and tracks unpacked from zips)
  downloads/audio/<folder...>/<file>.zip    audio bundles offered as downloads
  downloads/video/<folder...>/<file>.zip    video bundles offered as downloads
  video/<folder...>/<file>.mp4              web-ready video converted from AVI/FLV
  library/uploads/<yyyy>/<mm>/<file>       documents uploaded through the WordPress media library
  library/<kind>/<file>.pdf                 e-books, e-tracts, tracts
  images/<yyyy>/<mm>/<file>                 pictures from the WordPress media library
"""
import os
import re
import unicodedata


def slug(text: str, keep_dot: bool = True) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ")
    pattern = r"[^a-z0-9.]+" if keep_dot else r"[^a-z0-9]+"
    text = re.sub(pattern, "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-.")
    return text or "file"


def _slug_path(parts):
    return "/".join(slug(p, keep_dot=False) for p in parts)


def _slug_file(name: str) -> str:
    stem, dot, ext = name.rpartition(".")
    if not dot:
        return slug(name)
    return slug(stem, keep_dot=False) + "." + ext.lower()


def key_for_volume_path(path: str, *, video_as_mp4: bool = True) -> str:
    """Key for a path relative to the old uploads root (e.g. 'sjmathew/works/Audio/x/y.zip')."""
    parts = path.split("/")
    name = parts[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if parts[:2] == ["sjmathew", "works"] and len(parts) >= 4:
        area, sub = parts[2], parts[3:-1]
        if area == "video" and sub[:1] == ["files"]:
            sub = sub[1:]
        folder = _slug_path(sub)
        prefix = (folder + "/") if folder else ""
        if area == "Audio" or area == "ftp.sajumathew.net":
            if ext == "mp3":
                return "audio/" + prefix + _slug_file(name)
            return "downloads/audio/" + prefix + _slug_file(name)
        if area == "video":
            if ext in ("avi", "flv", "mp4", "wmv", "mpg"):
                base = _slug_file(name).rsplit(".", 1)[0]
                return "video/" + prefix + base + (".mp4" if video_as_mp4 else "." + ext)
            if ext == "mp3":
                return "audio/" + prefix + _slug_file(name)
            return "downloads/video/" + prefix + _slug_file(name)
        if area in ("eBooks", "eTracts", "tracts", "articles"):
            return "library/" + slug(area, keep_dot=False) + "/" + prefix + _slug_file(name)
    if parts[0] == "sjmathew" and len(parts) >= 4 and re.fullmatch(r"\d{4}", parts[1]) and re.fullmatch(r"\d{2}", parts[2]):
        kind = "images" if ext in ("jpg", "jpeg", "png", "gif", "webp", "svg", "ico") else "library/uploads"
        return "%s/%s/%s/%s" % (kind, parts[1], parts[2], _slug_file(name))
    return "other/" + _slug_path(parts[1:-1] if parts[0] == "sjmathew" else parts[:-1]) + "/" + _slug_file(name)


def key_for_theme_audio(path: str) -> str:
    """Key for an MP3 that lived in wp-content/themes/goodnews5/audio/<folder>/<file>."""
    parts = path.split("audio/", 1)[-1].split("/")
    return "audio/theme/" + _slug_path(parts[:-1]) + ("/" if len(parts) > 1 else "") + _slug_file(parts[-1])


def key_for_track(zip_path: str, member: str, index: int) -> str:
    """Key for an MP3 unpacked from a zip: audio/<zip folder>/<zip name>/<nn>-<track>.mp3"""
    parts = zip_path.split("/")
    zname = os.path.splitext(parts[-1])[0]
    folder = _slug_path(parts[3:-1]) if parts[:3] == ["sjmathew", "works", parts[2]] and len(parts) > 3 else ""
    base = os.path.splitext(os.path.basename(member))[0]
    return "audio/%s%s/%02d-%s.mp3" % ((folder + "/") if folder else "", slug(zname, keep_dot=False), index, slug(base, keep_dot=False))


if __name__ == "__main__":
    for p in [
        "sjmathew/works/Audio/ykt/Class 08.mp3",
        "sjmathew/works/Audio/His_Light_My_Life.zip",
        "sjmathew/works/video/files/icpf/Session_01.avi",
        "sjmathew/works/eBooks/Some Book.pdf",
        "sjmathew/2019/06/Bhoomiyile-Swargam-Book.pdf",
    ]:
        print("%-52s -> %s" % (p, key_for_volume_path(p)))
