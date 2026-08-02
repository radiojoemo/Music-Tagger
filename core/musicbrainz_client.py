"""
musicbrainz_client.py
Thin wrapper around musicbrainzngs for recording lookups and text search.
"""

import re

import musicbrainzngs as mb

_configured = False

_BAD_INCLUDE_RE = re.compile(r"Bad includes?:\s*(\S+)\s+is not a valid include")


def configure(contact_email: str = "you@example.com"):
    global _configured
    mb.set_useragent("MusicTagger", "1.0", contact_email)
    _configured = True


def _call_with_safe_includes(func, mbid, includes):
    """
    Calls a musicbrainzngs lookup function, automatically dropping any
    include the installed musicbrainzngs/MB API version rejects and
    retrying, instead of guessing a fixed 'valid' list up front (which
    varies by library/API version).

    musicbrainzngs raises its own InvalidIncludeError (not a plain
    ValueError) for this, and the exact exception class has varied across
    versions of the library — so this matches on the error *message*
    ("Bad includes: X is not a valid include") rather than a specific
    exception type, which works regardless of which class it's wrapped in.
    Returns {} if the call still fails for an unrelated reason.
    """
    remaining = list(includes)
    while True:
        try:
            return func(mbid, includes=remaining)
        except mb.WebServiceError:
            return {}
        except Exception as exc:
            match = _BAD_INCLUDE_RE.search(str(exc))
            if match and match.group(1) in remaining:
                remaining.remove(match.group(1))
                continue
            return {}


def search_recordings(artist: str, title: str, limit: int = 5) -> list:
    if not _configured:
        configure()
    try:
        result = mb.search_recordings(artist=artist, recording=title, limit=limit)
        return result.get("recording-list", [])
    except mb.WebServiceError:
        return []


def get_recording_by_id(mbid: str) -> dict:
    """
    NOTE: MusicBrainz only allows a limited set of includes on a recording
    lookup, and which ones are accepted can vary by musicbrainzngs/API
    version — 'release-groups' and 'labels' are release-level includes and
    commonly rejected here; 'genres' has also been rejected on some
    versions. Unsupported includes are dropped automatically (see
    _call_with_safe_includes); label/genre are filled in separately by
    enrich_tags_with_release(), which does a proper release lookup.
    """
    if not _configured:
        configure()
    result = _call_with_safe_includes(
        mb.get_recording_by_id, mbid,
        ["artists", "releases", "media", "artist-credits", "isrcs", "genres", "tags"],
    )
    return result.get("recording", {})


def get_release_by_id(release_id: str) -> dict:
    if not _configured:
        configure()
    result = _call_with_safe_includes(
        mb.get_release_by_id, release_id,
        ["labels", "recordings", "release-groups", "genres", "tags"],
    )
    return result.get("release", {})


def enrich_tags_with_release(tags: dict) -> dict:
    """
    Fills in label, catalog number, and genre from a full release lookup.
    A recording lookup can't request 'labels' or 'release-groups', so this
    does a second, release-level call (valid includes there) whenever those
    fields are still missing after recording_to_tags().
    """
    album_id = tags.get("musicbrainz_albumid")
    if not album_id:
        return tags

    release = get_release_by_id(album_id)
    if not release:
        return tags

    if not tags.get("label"):
        label_info_list = release.get("label-info-list", [])
        if label_info_list:
            label_info = label_info_list[0]
            tags["label"] = label_info.get("label", {}).get("name", "")
            tags["catalognumber"] = label_info.get("catalog-number", "")

    if not tags.get("genre"):
        genre = _extract_genre(release)
        if not genre:
            genre = _extract_genre(release.get("release-group", {}))
        tags["genre"] = genre

    if not tags.get("date"):
        tags["date"] = release.get("date", "")

    return tags


def recording_to_tags(recording: dict) -> dict:
    """
    Convert a MusicBrainz recording dict (from search or lookup) into our
    normalized tag dict. Picks the first associated release for album-level
    fields (label, catalog number, date) when available.
    """
    tags = {
        "artist": "", "title": "", "album": "", "albumartist": "",
        "date": "", "tracknumber": "", "discnumber": "", "genre": "",
        "label": "", "catalognumber": "", "isrc": "",
        "musicbrainz_trackid": recording.get("id", ""),
        "musicbrainz_albumid": "", "musicbrainz_artistid": "",
    }

    tags["title"] = recording.get("title", "")

    isrc_list = recording.get("isrc-list", [])
    if isrc_list:
        tags["isrc"] = isrc_list[0]

    tags["genre"] = _extract_genre(recording)

    artist_credit = recording.get("artist-credit", [])
    if artist_credit:
        parts = []
        for entry in artist_credit:
            if isinstance(entry, dict) and "artist" in entry:
                parts.append(entry["artist"].get("name", "") + entry.get("joinphrase", ""))
                if not tags["musicbrainz_artistid"]:
                    tags["musicbrainz_artistid"] = entry["artist"].get("id", "")
            elif isinstance(entry, str):
                parts.append(entry)
        tags["artist"] = "".join(parts)

    releases = recording.get("release-list", [])
    if releases:
        release = releases[0]
        tags["album"] = release.get("title", "")
        tags["musicbrainz_albumid"] = release.get("id", "")
        tags["date"] = release.get("date", "")

        media = release.get("medium-list", [])
        if media:
            tags["discnumber"] = str(media[0].get("position", ""))
            tracks = media[0].get("track-list", [])
            if tracks:
                tags["tracknumber"] = tracks[0].get("number", "")

    return tags


def _extract_genre(entity: dict) -> str:
    """
    Pulls a genre string from an entity's curated genre-list (preferred) or
    falls back to its folksonomy tag-list, picking the highest-voted/most
    common entry. Returns "" if neither is present (requires the 'genres'
    and 'tags' includes to have been requested).
    """
    genre_list = entity.get("genre-list", [])
    if genre_list:
        best = max(genre_list, key=lambda g: int(g.get("count", 0)))
        return best.get("name", "")

    tag_list = entity.get("tag-list", [])
    if tag_list:
        best = max(tag_list, key=lambda t: int(t.get("count", 0)))
        return best.get("name", "")

    return ""
