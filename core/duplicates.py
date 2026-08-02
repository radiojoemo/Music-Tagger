"""
duplicates.py
Finds duplicate tracks in the library using three signals, most reliable
first:

  1. Identical local Chromaprint fingerprint -> same audio content
  2. Same MusicBrainz recording ID -> same recording, possibly re-encoded
  3. Fuzzy artist+title match (+ duration proximity if known) -> catches
     duplicates that were never fingerprinted/matched

Operates on whatever's already in the SQLite library (see database.py) so
it works across your whole collection, not just the current scan folder.
"""

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from . import database

DURATION_TOLERANCE_SEC = 3.0
FUZZY_THRESHOLD = 92


@dataclass
class DuplicateGroup:
    reason: str
    tracks: list = field(default_factory=list)


def find_duplicates(tracks: list = None) -> list:
    if tracks is None:
        tracks = database.get_all_tracks()

    groups = []
    used_path_sets = set()

    # --- 1. Exact fingerprint match ---
    fp_map = {}
    for t in tracks:
        fp = t.get("fingerprint") or ""
        if fp:
            fp_map.setdefault(fp, []).append(t)
    for fp, group in fp_map.items():
        if len(group) > 1:
            key = frozenset(t["filepath"] for t in group)
            if key not in used_path_sets:
                groups.append(DuplicateGroup(reason="Identical audio (fingerprint match)", tracks=group))
                used_path_sets.add(key)

    # --- 2. Same MusicBrainz recording ---
    mbid_map = {}
    for t in tracks:
        mbid = t.get("musicbrainz_trackid") or ""
        if mbid:
            mbid_map.setdefault(mbid, []).append(t)
    for mbid, group in mbid_map.items():
        if len(group) > 1:
            key = frozenset(t["filepath"] for t in group)
            if key not in used_path_sets:
                groups.append(DuplicateGroup(reason="Same MusicBrainz recording", tracks=group))
                used_path_sets.add(key)

    # --- 3. Fuzzy artist+title match (fallback) ---
    checked_pairs = set()
    already_grouped = set()
    for group in groups:
        for t in group.tracks:
            already_grouped.add(t["filepath"])

    fuzzy_groups = {}  # representative filepath -> DuplicateGroup
    for i, t1 in enumerate(tracks):
        if not t1.get("artist") or not t1.get("title"):
            continue
        for t2 in tracks[i + 1:]:
            if not t2.get("artist") or not t2.get("title"):
                continue
            pair_key = tuple(sorted([t1["filepath"], t2["filepath"]]))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            if t1["filepath"] in already_grouped and t2["filepath"] in already_grouped:
                continue  # already accounted for by a stronger signal

            artist_score = fuzz.token_sort_ratio(t1["artist"], t2["artist"])
            title_score = fuzz.token_sort_ratio(t1["title"], t2["title"])
            if artist_score < FUZZY_THRESHOLD or title_score < FUZZY_THRESHOLD:
                continue

            dur1, dur2 = t1.get("duration") or 0, t2.get("duration") or 0
            if dur1 and dur2 and abs(dur1 - dur2) > DURATION_TOLERANCE_SEC:
                continue

            # Merge into an existing fuzzy group if either track is already in one
            existing_key = None
            for rep, grp in fuzzy_groups.items():
                paths = {t["filepath"] for t in grp.tracks}
                if t1["filepath"] in paths or t2["filepath"] in paths:
                    existing_key = rep
                    break
            if existing_key:
                grp = fuzzy_groups[existing_key]
                paths = {t["filepath"] for t in grp.tracks}
                if t1["filepath"] not in paths:
                    grp.tracks.append(t1)
                if t2["filepath"] not in paths:
                    grp.tracks.append(t2)
            else:
                fuzzy_groups[t1["filepath"]] = DuplicateGroup(
                    reason="Similar artist/title", tracks=[t1, t2]
                )

    groups.extend(fuzzy_groups.values())
    return groups
