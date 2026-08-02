"""
coverart.py
Fetches front cover art bytes for a matched track:

  1. Cover Art Archive (linked to MusicBrainz releases) — free, no API key
  2. Discogs release images — used as a fallback when a Discogs match was
     used, or MusicBrainz has no art for that release

Returns (image_bytes, mime_type) or (None, None) if unavailable.
"""

import requests

CAA_BASE = "https://coverartarchive.org"
DISCOGS_BASE = "https://api.discogs.com"
USER_AGENT = "MusicTagger/1.0 (+https://github.com/yourname/music-tagger)"


def fetch_from_musicbrainz(release_mbid: str):
    if not release_mbid:
        return None, None
    try:
        resp = requests.get(
            f"{CAA_BASE}/release/{release_mbid}/front",
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        if resp.status_code == 200 and resp.content:
            mime = resp.headers.get("Content-Type", "image/jpeg")
            return resp.content, mime
    except requests.RequestException:
        pass
    return None, None


def fetch_from_discogs(release_id, token: str):
    if not release_id or not token:
        return None, None
    try:
        resp = requests.get(
            f"{DISCOGS_BASE}/releases/{release_id}",
            params={"token": token},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        images = data.get("images", [])
        if not images:
            return None, None

        primary = next((img for img in images if img.get("type") == "primary"), images[0])
        url = primary.get("resource_url") or primary.get("uri")
        if not url:
            return None, None

        img_resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if img_resp.status_code == 200 and img_resp.content:
            mime = img_resp.headers.get("Content-Type", "image/jpeg")
            return img_resp.content, mime
    except requests.RequestException:
        pass
    return None, None


def fetch_cover_art(mbid: str = "", discogs_release_id=None, discogs_token: str = ""):
    """
    Tries MusicBrainz first (free, no key needed), then Discogs as a
    fallback. Returns (image_bytes, mime_type) or (None, None).
    """
    if mbid:
        image_bytes, mime = fetch_from_musicbrainz(mbid)
        if image_bytes:
            return image_bytes, mime

    if discogs_release_id and discogs_token:
        image_bytes, mime = fetch_from_discogs(discogs_release_id, discogs_token)
        if image_bytes:
            return image_bytes, mime

    return None, None
