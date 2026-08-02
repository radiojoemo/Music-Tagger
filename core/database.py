"""
database.py
SQLite-backed local library: every scanned/tagged track gets an entry, and
every tag write is logged to tag_history under a batch_id so a whole
processing run can be undone at once.

DB file lives alongside config.json in the user's AppData folder.
"""

import os
import json
import sqlite3
import uuid
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    artist TEXT, title TEXT, album TEXT, albumartist TEXT,
    date TEXT, tracknumber TEXT, discnumber TEXT, genre TEXT,
    label TEXT, catalognumber TEXT, isrc TEXT,
    musicbrainz_trackid TEXT, musicbrainz_albumid TEXT, musicbrainz_artistid TEXT,
    fingerprint TEXT, duration REAL, file_size INTEGER,
    match_source TEXT, confidence REAL,
    last_scanned TEXT
);

CREATE TABLE IF NOT EXISTS tag_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    filepath TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    old_tags TEXT,
    new_tags TEXT,
    undone INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
CREATE INDEX IF NOT EXISTS idx_history_batch ON tag_history(batch_id);
"""


def _db_path() -> str:
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "MusicTagger")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "library.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after initial release to existing databases."""
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(tracks)")}
    if "isrc" not in existing_cols:
        conn.execute("ALTER TABLE tracks ADD COLUMN isrc TEXT")
        conn.commit()


def new_batch_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"


def upsert_track(filepath: str, tags: dict, fingerprint: str = "", duration: float = 0.0,
                  match_source: str = "", confidence: float = 0.0) -> None:
    conn = get_connection()
    try:
        file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        conn.execute("""
            INSERT INTO tracks (filepath, artist, title, album, albumartist, date,
                tracknumber, discnumber, genre, label, catalognumber, isrc,
                musicbrainz_trackid, musicbrainz_albumid, musicbrainz_artistid,
                fingerprint, duration, file_size, match_source, confidence, last_scanned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filepath) DO UPDATE SET
                artist=excluded.artist, title=excluded.title, album=excluded.album,
                albumartist=excluded.albumartist, date=excluded.date,
                tracknumber=excluded.tracknumber, discnumber=excluded.discnumber,
                genre=excluded.genre, label=excluded.label, catalognumber=excluded.catalognumber,
                isrc=excluded.isrc,
                musicbrainz_trackid=excluded.musicbrainz_trackid,
                musicbrainz_albumid=excluded.musicbrainz_albumid,
                musicbrainz_artistid=excluded.musicbrainz_artistid,
                fingerprint=excluded.fingerprint, duration=excluded.duration,
                file_size=excluded.file_size, match_source=excluded.match_source,
                confidence=excluded.confidence, last_scanned=excluded.last_scanned
        """, (
            filepath, tags.get("artist", ""), tags.get("title", ""), tags.get("album", ""),
            tags.get("albumartist", ""), tags.get("date", ""), tags.get("tracknumber", ""),
            tags.get("discnumber", ""), tags.get("genre", ""), tags.get("label", ""),
            tags.get("catalognumber", ""), tags.get("isrc", ""),
            tags.get("musicbrainz_trackid", ""),
            tags.get("musicbrainz_albumid", ""), tags.get("musicbrainz_artistid", ""),
            fingerprint, duration or 0.0, file_size, match_source, confidence or 0.0,
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()


def remove_track(filepath: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM tracks WHERE filepath = ?", (filepath,))
        conn.commit()
    finally:
        conn.close()


def get_all_tracks(query: str = "") -> list:
    conn = get_connection()
    try:
        if query:
            like = f"%{query}%"
            rows = conn.execute("""
                SELECT * FROM tracks
                WHERE artist LIKE ? OR title LIKE ? OR album LIKE ? OR filepath LIKE ?
                ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE, tracknumber
            """, (like, like, like, like)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM tracks
                ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE, tracknumber
            """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_library_stats() -> dict:
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) c FROM tracks").fetchone()["c"]
        artists = conn.execute(
            "SELECT COUNT(DISTINCT artist) c FROM tracks WHERE artist != ''"
        ).fetchone()["c"]
        albums = conn.execute(
            "SELECT COUNT(DISTINCT album) c FROM tracks WHERE album != ''"
        ).fetchone()["c"]
        return {"tracks": total, "artists": artists, "albums": albums}
    finally:
        conn.close()


def record_tag_history(batch_id: str, filepath: str, old_tags: dict, new_tags: dict) -> None:
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO tag_history (batch_id, filepath, timestamp, old_tags, new_tags, undone)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (
            batch_id, filepath, datetime.now(timezone.utc).isoformat(),
            json.dumps(old_tags), json.dumps(new_tags),
        ))
        conn.commit()
    finally:
        conn.close()


def clear_matching_field_value(fields: list, value: str) -> int:
    """
    Blanks out the given fields (e.g. ['label', 'catalognumber']) wherever
    their current value matches `value` case-insensitively (trimmed) —
    for retroactively scrubbing a *specific known* junk value, e.g. a
    scene-release/download-site name like "PMEDIA". Returns the number of
    rows affected (a track counts once even if multiple fields on it
    matched). See sanitize_unmatched_library() for the broader, not
    value-specific fix.
    """
    target = value.strip().lower()
    if not target or not fields:
        return 0

    conn = get_connection()
    try:
        rows = conn.execute("SELECT filepath, " + ", ".join(fields) + " FROM tracks").fetchall()
        affected = 0
        for row in rows:
            updates = {}
            for field in fields:
                current = (row[field] or "").strip().lower()
                if current == target:
                    updates[field] = ""
            if updates:
                set_clause = ", ".join(f"{field} = ?" for field in updates)
                conn.execute(
                    f"UPDATE tracks SET {set_clause} WHERE filepath = ?",
                    (*updates.values(), row["filepath"]),
                )
                affected += 1
        conn.commit()
        return affected
    finally:
        conn.close()


# Fields never trusted unless they came from an actual MusicBrainz/Discogs
# match — see sanitize_unmatched_library() below.
UNTRUSTED_FIELDS = [
    "label", "catalognumber", "genre", "isrc",
    "musicbrainz_trackid", "musicbrainz_albumid", "musicbrainz_artistid",
]


def sanitize_unmatched_library() -> int:
    """
    Blanks label/catalog#/genre/ISRC/MusicBrainz-ID fields for every track
    whose match_source is empty — i.e. it was never actually matched
    against MusicBrainz/Discogs in this app. This is the blanket fix for
    "assume anything not confirmed by the API is untrustworthy", rather
    than clearing one known-bad value at a time: those fields on an
    unmatched track can only be leftovers from the file's own (unverified)
    existing tags, possibly written by something else entirely before this
    app ever touched the file. Returns the number of rows updated.
    """
    conn = get_connection()
    try:
        blank_check = " OR ".join(f"{f} != ''" for f in UNTRUSTED_FIELDS)
        rows = conn.execute(
            f"SELECT filepath FROM tracks "
            f"WHERE (match_source IS NULL OR match_source = '') AND ({blank_check})"
        ).fetchall()
        if rows:
            set_clause = ", ".join(f"{f} = ''" for f in UNTRUSTED_FIELDS)
            conn.execute(
                f"UPDATE tracks SET {set_clause} "
                f"WHERE (match_source IS NULL OR match_source = '')"
            )
            conn.commit()
        return len(rows)
    finally:
        conn.close()


def get_batches() -> list:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT batch_id,
                   MIN(timestamp) AS started,
                   COUNT(*) AS file_count,
                   SUM(CASE WHEN undone = 1 THEN 1 ELSE 0 END) AS undone_count
            FROM tag_history
            GROUP BY batch_id
            ORDER BY started DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_batch_entries(batch_id: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tag_history WHERE batch_id = ? ORDER BY id", (batch_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["old_tags"] = json.loads(d["old_tags"]) if d["old_tags"] else {}
            d["new_tags"] = json.loads(d["new_tags"]) if d["new_tags"] else {}
            result.append(d)
        return result
    finally:
        conn.close()


def mark_batch_undone(batch_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE tag_history SET undone = 1 WHERE batch_id = ?", (batch_id,))
        conn.commit()
    finally:
        conn.close()
