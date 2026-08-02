"""
discogs_client.py
Minimal Discogs API v2 client using requests. Requires a personal access
token (see README for how to obtain one).
"""

import requests

BASE_URL = "https://api.discogs.com"
USER_AGENT = "MusicTagger/1.0 (+https://github.com/yourname/music-tagger)"


class DiscogsClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {"User-Agent": USER_AGENT}

    def search(self, artist: str = "", track: str = "", release_title: str = "", per_page: int = 5) -> list:
        if not self.token:
            return []
        params = {"type": "release", "per_page": per_page, "token": self.token}
        if artist:
            params["artist"] = artist
        if track:
            params["track"] = track
        if release_title:
            params["release_title"] = release_title
        try:
            resp = requests.get(f"{BASE_URL}/database/search", params=params,
                                 headers=self.headers, timeout=15)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except requests.RequestException:
            return []

    def get_release(self, release_id) -> dict:
        if not self.token:
            return {}
        try:
            resp = requests.get(f"{BASE_URL}/releases/{release_id}",
                                 params={"token": self.token}, headers=self.headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {}


def release_to_tags(release: dict) -> dict:
    """
    Convert a full Discogs release dict (from get_release) into our
    normalized tag dict.
    """
    tags = {
        "artist": "", "title": "", "album": release.get("title", ""),
        "albumartist": "", "date": str(release.get("year", "") or ""),
        "tracknumber": "", "discnumber": "", "genre": "",
        "label": "", "catalognumber": "", "isrc": "",
        "musicbrainz_trackid": "", "musicbrainz_albumid": "", "musicbrainz_artistid": "",
    }

    # Discogs doesn't have a dedicated ISRC field, but some releases list it
    # under "identifiers" (usually release-level, not per-track).
    for identifier in release.get("identifiers", []):
        if "isrc" in identifier.get("type", "").lower():
            tags["isrc"] = identifier.get("value", "").replace("-", "").replace(" ", "")
            break

    artists = release.get("artists", [])
    if artists:
        tags["artist"] = ", ".join(a.get("name", "").strip() for a in artists)
        tags["albumartist"] = tags["artist"]

    genres = release.get("genres", []) or release.get("styles", [])
    if genres:
        tags["genre"] = ", ".join(genres)

    labels = release.get("labels", [])
    if labels:
        tags["label"] = labels[0].get("name", "")
        tags["catalognumber"] = labels[0].get("catno", "")

    return tags


def release_track_to_tags(release: dict, track_position: str) -> dict:
    """
    Same as release_to_tags but also fills in title/tracknumber for a
    specific track position (e.g. 'A1' or '3') found in the release's
    tracklist.
    """
    tags = release_to_tags(release)
    for idx, track in enumerate(release.get("tracklist", []), start=1):
        if track.get("position") == track_position:
            tags["title"] = track.get("title", "")
            tags["tracknumber"] = str(idx)
            break
    return tags
