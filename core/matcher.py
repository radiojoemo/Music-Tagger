"""
matcher.py
Orchestrates the matching pipeline for a single audio file:

  1. Acoustic fingerprint match (AcoustID -> MusicBrainz recording) if an
     AcoustID API key is configured and fpcalc is available.
  2. Fallback: MusicBrainz text search using existing tags / filename.
  3. Fallback: Discogs text search.

Returns a MatchResult with a 0-100 confidence score so the caller can decide
whether to auto-write or send to manual review.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz

from . import musicbrainz_client as mbc
from . import discogs_client
from . import fingerprint


@dataclass
class MatchResult:
    source: str                # 'fingerprint', 'musicbrainz-text', 'discogs-text'
    confidence: float          # 0-100
    tags: dict
    mbid: Optional[str] = None
    discogs_release_id: Optional[str] = None
    candidates: list = field(default_factory=list)  # alternate candidates for review UI


def guess_artist_title_from_filename(filepath: str) -> tuple:
    """
    Best-effort extraction of (artist, title) from a filename like
    'Artist - Title.mp3' when tags are missing.
    """
    name = os.path.splitext(os.path.basename(filepath))[0]
    name = re.sub(r"^\d+[\.\-\s]+", "", name)  # strip leading track numbers
    if " - " in name:
        artist, title = name.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", name.strip()


def match_file(filepath: str, current_tags: dict, acoustid_key: str = "",
                discogs_token: str = "", fpcalc_path: str = "") -> Optional[MatchResult]:

    query_artist = current_tags.get("artist", "") or ""
    query_title = current_tags.get("title", "") or ""
    if not query_artist or not query_title:
        guess_artist, guess_title = guess_artist_title_from_filename(filepath)
        query_artist = query_artist or guess_artist
        query_title = query_title or guess_title

    # --- 1. Acoustic fingerprint ---
    if acoustid_key:
        try:
            fp_results = fingerprint.match_file(filepath, acoustid_key, fpcalc_path)
        except fingerprint.FpcalcNotFoundError:
            fp_results = []

        if fp_results:
            score, recording_id, title, artist = fp_results[0]
            recording = mbc.get_recording_by_id(recording_id)
            if recording:
                tags = mbc.recording_to_tags(recording)
                tags = mbc.enrich_tags_with_release(tags)
                return MatchResult(
                    source="fingerprint",
                    confidence=round(score * 100, 1),
                    tags=tags,
                    mbid=recording_id,
                    candidates=fp_results[1:5],
                )

    # --- 2. MusicBrainz text search fallback ---
    if query_artist and query_title:
        candidates = mbc.search_recordings(query_artist, query_title, limit=5)
        if candidates:
            best = candidates[0]
            # The search endpoint only returns lightweight fields (no label,
            # genre, or full ISRC data) — do a full lookup on the top hit to
            # get everything a fingerprint match would have.
            full_recording = mbc.get_recording_by_id(best.get("id")) or best
            tags = mbc.recording_to_tags(full_recording)
            tags = mbc.enrich_tags_with_release(tags)
            score = _text_confidence(query_artist, query_title, tags.get("artist", ""), tags.get("title", ""))
            return MatchResult(
                source="musicbrainz-text",
                confidence=score,
                tags=tags,
                mbid=best.get("id"),
                candidates=candidates[1:5],
            )

    # --- 3. Discogs text search fallback ---
    if discogs_token and query_artist and query_title:
        client = discogs_client.DiscogsClient(discogs_token)
        results = client.search(artist=query_artist, track=query_title)
        if results:
            best = results[0]
            release = client.get_release(best["id"])
            if release:
                tags = discogs_client.release_track_to_tags(release, "")
                # if track title wasn't matched by position, at least fill album-level info
                if not tags.get("title"):
                    tags["title"] = query_title
                if not tags.get("artist"):
                    tags["artist"] = query_artist
                score = _text_confidence(query_artist, query_title, tags.get("artist", ""), tags.get("title", ""))
                return MatchResult(
                    source="discogs-text",
                    confidence=score,
                    tags=tags,
                    discogs_release_id=best["id"],
                    candidates=results[1:5],
                )

    return None


def _text_confidence(q_artist, q_title, r_artist, r_title) -> float:
    artist_score = fuzz.token_sort_ratio(q_artist, r_artist)
    title_score = fuzz.token_sort_ratio(q_title, r_title)
    # Weight title slightly higher since it's the more distinctive field
    return round((artist_score * 0.4 + title_score * 0.6), 1)


def sanitize_unmatched_tags(tags: dict) -> dict:
    """
    Blanks out fields that are only trustworthy when they came from an
    actual MusicBrainz/Discogs match — label, catalog number, genre, ISRC,
    and MusicBrainz IDs. Used whenever a file's *existing* tags (as read
    straight off the file) are about to be shown or stored without having
    been confirmed against a real match. This exists because plenty of
    files in the wild carry junk in exactly these fields — most commonly a
    scene-release or download-site name stuffed into the label field
    (e.g. "PMEDIA") — and the app should never surface or persist that as
    if it were real metadata.

    Artist/title/album/date/track/disc are left alone since they're the
    file's basic identity, not a common junk-injection target.
    """
    from . import tagger  # local import avoids a module-load-order cycle

    sanitized = dict(tags)
    for field in tagger.UNTRUSTED_UNTIL_MATCHED:
        sanitized[field] = ""
    sanitized["musicbrainz_trackid"] = ""
    sanitized["musicbrainz_albumid"] = ""
    sanitized["musicbrainz_artistid"] = ""
    return sanitized
