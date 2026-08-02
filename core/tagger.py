"""
tagger.py
Reads and writes normalized tag data across MP3 (ID3), FLAC, and MP4 (M4A/AAC)
files. Other formats (ogg, wma, wav) get best-effort handling through mutagen's
generic EasyTags interface.

IMPORTANT: every write function here clears a field when the new value is
empty, rather than leaving whatever was already in the file untouched. This
matters because plenty of MP3s in the wild carry junk metadata injected by
whatever tool ripped/shared them (a common example: a scene-release or
download-site name shoved into the label/publisher field). Once this app
writes a match, the file should reflect *only* what MusicBrainz/Discogs
actually provided — not a mix of new data plus leftover junk from before.

Normalized tag dict keys used throughout this app:
    artist, title, album, albumartist, date, tracknumber, discnumber, genre,
    label, catalognumber, isrc, musicbrainz_trackid, musicbrainz_albumid,
    musicbrainz_artistid
"""

import os

from mutagen import File as MutagenFile
from mutagen.id3 import (
    ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TPE2, TDRC, TRCK, TPOS, TCON,
    TSRC, TXXX, APIC,
)
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover

NORMALIZED_KEYS = [
    "artist", "title", "album", "albumartist", "date", "tracknumber",
    "discnumber", "genre", "label", "catalognumber", "isrc",
    "musicbrainz_trackid", "musicbrainz_albumid", "musicbrainz_artistid",
]

# Fields prone to junk injection by scene-release/download-site tools
# (e.g. a site or group name written into the label/publisher field).
# Only ever populated from an actual MusicBrainz/Discogs match — see
# matcher.sanitize_unmatched_tags(), which the app calls before storing or
# displaying anything for a file that hasn't been matched yet.
UNTRUSTED_UNTIL_MATCHED = ["label", "catalognumber", "genre", "isrc"]


def read_tags(filepath: str) -> dict:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mp3":
        return _read_id3(filepath)
    if ext == ".flac":
        return _read_flac(filepath)
    if ext in (".m4a", ".aac"):
        return _read_mp4(filepath)
    return _read_generic(filepath)


def write_tags(filepath: str, tags: dict, cover_bytes: bytes = None, cover_mime: str = "image/jpeg") -> None:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mp3":
        _write_id3(filepath, tags, cover_bytes, cover_mime)
    elif ext == ".flac":
        _write_flac(filepath, tags, cover_bytes, cover_mime)
    elif ext in (".m4a", ".aac"):
        _write_mp4(filepath, tags, cover_bytes, cover_mime)
    else:
        _write_generic(filepath, tags)


# ---------------------------------------------------------------- MP3 / ID3

def _read_id3(filepath: str) -> dict:
    try:
        id3 = ID3(filepath)
    except ID3NoHeaderError:
        return {k: "" for k in NORMALIZED_KEYS}

    def txxx(desc):
        frames = id3.getall("TXXX:" + desc)
        return frames[0].text[0] if frames else ""

    return {
        "artist": _first(id3, "TPE1"),
        "title": _first(id3, "TIT2"),
        "album": _first(id3, "TALB"),
        "albumartist": _first(id3, "TPE2"),
        "date": _first(id3, "TDRC"),
        "tracknumber": _first(id3, "TRCK"),
        "discnumber": _first(id3, "TPOS"),
        "genre": _first(id3, "TCON"),
        "label": txxx("LABEL"),
        "catalognumber": txxx("CATALOGNUMBER"),
        "isrc": _first(id3, "TSRC"),
        "musicbrainz_trackid": txxx("MusicBrainz Release Track Id") or txxx("MusicBrainz Track Id"),
        "musicbrainz_albumid": txxx("MusicBrainz Album Id"),
        "musicbrainz_artistid": txxx("MusicBrainz Artist Id"),
    }


def _first(id3, frame_id):
    frame = id3.get(frame_id)
    return str(frame.text[0]) if frame and frame.text else ""


def _write_id3(filepath: str, tags: dict, cover_bytes, cover_mime) -> None:
    try:
        id3 = ID3(filepath)
    except ID3NoHeaderError:
        id3 = ID3()

    def set_text_frame(frame_id, frame_cls, value):
        # Always clear first, then re-add only if there's a real value —
        # so an empty match result actually erases whatever was there.
        id3.delall(frame_id)
        if value:
            id3.setall(frame_id, [frame_cls(encoding=3, text=[value])])

    def set_txxx(desc, value):
        id3.delall("TXXX:" + desc)
        if value:
            id3.add(TXXX(encoding=3, desc=desc, text=[value]))

    set_text_frame("TPE1", TPE1, tags.get("artist", ""))
    set_text_frame("TIT2", TIT2, tags.get("title", ""))
    set_text_frame("TALB", TALB, tags.get("album", ""))
    set_text_frame("TPE2", TPE2, tags.get("albumartist", ""))
    set_text_frame("TDRC", TDRC, tags.get("date", ""))
    set_text_frame("TRCK", TRCK, tags.get("tracknumber", ""))
    set_text_frame("TPOS", TPOS, tags.get("discnumber", ""))
    set_text_frame("TCON", TCON, tags.get("genre", ""))
    set_text_frame("TSRC", TSRC, tags.get("isrc", ""))

    set_txxx("LABEL", tags.get("label", ""))
    set_txxx("CATALOGNUMBER", tags.get("catalognumber", ""))
    set_txxx("MusicBrainz Release Track Id", tags.get("musicbrainz_trackid", ""))
    set_txxx("MusicBrainz Album Id", tags.get("musicbrainz_albumid", ""))
    set_txxx("MusicBrainz Artist Id", tags.get("musicbrainz_artistid", ""))

    if cover_bytes:
        id3.delall("APIC")
        id3.add(APIC(encoding=3, mime=cover_mime, type=3, desc="Cover", data=cover_bytes))

    id3.save(filepath, v2_version=3)


# ---------------------------------------------------------------- FLAC

def _read_flac(filepath: str) -> dict:
    audio = FLAC(filepath)

    def get(key):
        vals = audio.get(key)
        return vals[0] if vals else ""

    return {
        "artist": get("artist"),
        "title": get("title"),
        "album": get("album"),
        "albumartist": get("albumartist"),
        "date": get("date"),
        "tracknumber": get("tracknumber"),
        "discnumber": get("discnumber"),
        "genre": get("genre"),
        "label": get("label"),
        "catalognumber": get("catalognumber"),
        "isrc": get("isrc"),
        "musicbrainz_trackid": get("musicbrainz_trackid"),
        "musicbrainz_albumid": get("musicbrainz_albumid"),
        "musicbrainz_artistid": get("musicbrainz_artistid"),
    }


def _write_flac(filepath: str, tags: dict, cover_bytes, cover_mime) -> None:
    audio = FLAC(filepath)

    mapping = {
        "artist": "artist", "title": "title", "album": "album",
        "albumartist": "albumartist", "date": "date",
        "tracknumber": "tracknumber", "discnumber": "discnumber",
        "genre": "genre", "label": "label", "catalognumber": "catalognumber",
        "isrc": "isrc",
        "musicbrainz_trackid": "musicbrainz_trackid",
        "musicbrainz_albumid": "musicbrainz_albumid",
        "musicbrainz_artistid": "musicbrainz_artistid",
    }
    for norm_key, flac_key in mapping.items():
        value = tags.get(norm_key, "")
        if value:
            audio[flac_key] = value
        elif flac_key in audio:
            del audio[flac_key]

    if cover_bytes:
        audio.clear_pictures()
        pic = Picture()
        pic.data = cover_bytes
        pic.type = 3
        pic.mime = cover_mime
        audio.add_picture(pic)

    audio.save()


# ---------------------------------------------------------------- MP4 / M4A

def _read_mp4(filepath: str) -> dict:
    audio = MP4(filepath)

    def atom(key):
        vals = audio.tags.get(key) if audio.tags else None
        return str(vals[0]) if vals else ""

    def freeform(name):
        key = f"----:com.apple.iTunes:{name}"
        vals = audio.tags.get(key) if audio.tags else None
        if vals:
            return vals[0].decode("utf-8", errors="ignore")
        return ""

    trkn = audio.tags.get("trkn") if audio.tags else None
    disk = audio.tags.get("disk") if audio.tags else None

    return {
        "artist": atom("\xa9ART"),
        "title": atom("\xa9nam"),
        "album": atom("\xa9alb"),
        "albumartist": atom("aART"),
        "date": atom("\xa9day"),
        "tracknumber": str(trkn[0][0]) if trkn else "",
        "discnumber": str(disk[0][0]) if disk else "",
        "genre": atom("\xa9gen"),
        "label": freeform("LABEL"),
        "catalognumber": freeform("CATALOGNUMBER"),
        "isrc": freeform("ISRC"),
        "musicbrainz_trackid": freeform("MusicBrainz Track Id"),
        "musicbrainz_albumid": freeform("MusicBrainz Album Id"),
        "musicbrainz_artistid": freeform("MusicBrainz Artist Id"),
    }


def _write_mp4(filepath: str, tags: dict, cover_bytes, cover_mime) -> None:
    audio = MP4(filepath)
    if audio.tags is None:
        audio.add_tags()

    def set_atom(key, value):
        if value:
            audio.tags[key] = [value]
        elif key in audio.tags:
            del audio.tags[key]

    set_atom("\xa9ART", tags.get("artist", ""))
    set_atom("\xa9nam", tags.get("title", ""))
    set_atom("\xa9alb", tags.get("album", ""))
    set_atom("aART", tags.get("albumartist", ""))
    set_atom("\xa9day", tags.get("date", ""))
    set_atom("\xa9gen", tags.get("genre", ""))

    if tags.get("tracknumber"):
        try:
            audio.tags["trkn"] = [(int(tags["tracknumber"]), 0)]
        except ValueError:
            pass
    elif "trkn" in audio.tags:
        del audio.tags["trkn"]

    if tags.get("discnumber"):
        try:
            audio.tags["disk"] = [(int(tags["discnumber"]), 0)]
        except ValueError:
            pass
    elif "disk" in audio.tags:
        del audio.tags["disk"]

    def set_freeform(name, value):
        key = f"----:com.apple.iTunes:{name}"
        if value:
            audio.tags[key] = [value.encode("utf-8")]
        elif key in audio.tags:
            del audio.tags[key]

    set_freeform("LABEL", tags.get("label", ""))
    set_freeform("CATALOGNUMBER", tags.get("catalognumber", ""))
    set_freeform("ISRC", tags.get("isrc", ""))
    set_freeform("MusicBrainz Track Id", tags.get("musicbrainz_trackid", ""))
    set_freeform("MusicBrainz Album Id", tags.get("musicbrainz_albumid", ""))
    set_freeform("MusicBrainz Artist Id", tags.get("musicbrainz_artistid", ""))

    if cover_bytes:
        fmt = MP4Cover.FORMAT_PNG if cover_mime == "image/png" else MP4Cover.FORMAT_JPEG
        audio.tags["covr"] = [MP4Cover(cover_bytes, imageformat=fmt)]

    audio.save()


# ---------------------------------------------------------------- Generic fallback (ogg, wma, wav)

def _read_generic(filepath: str) -> dict:
    audio = MutagenFile(filepath, easy=True)
    if audio is None or audio.tags is None:
        return {k: "" for k in NORMALIZED_KEYS}

    def get(key):
        vals = audio.tags.get(key)
        return vals[0] if vals else ""

    return {
        "artist": get("artist"),
        "title": get("title"),
        "album": get("album"),
        "albumartist": get("albumartist"),
        "date": get("date"),
        "tracknumber": get("tracknumber"),
        "discnumber": get("discnumber"),
        "genre": get("genre"),
        "label": "",
        "catalognumber": "",
        "isrc": "",
        "musicbrainz_trackid": "",
        "musicbrainz_albumid": "",
        "musicbrainz_artistid": "",
    }


def _write_generic(filepath: str, tags: dict) -> None:
    audio = MutagenFile(filepath, easy=True)
    if audio is None:
        return
    if audio.tags is None:
        audio.add_tags()

    for key in ("artist", "title", "album", "albumartist", "date",
                "tracknumber", "discnumber", "genre"):
        value = tags.get(key, "")
        try:
            if value:
                audio.tags[key] = value
            elif key in audio.tags:
                del audio.tags[key]
        except Exception:
            pass
    audio.save()
