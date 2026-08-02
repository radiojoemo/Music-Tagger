"""
fingerprint.py
Acoustic fingerprinting via Chromaprint (fpcalc) + AcoustID lookup, using
the pyacoustid library. Requires fpcalc.exe available (see README).
"""

import os
import acoustid


class FpcalcNotFoundError(Exception):
    pass


def _apply_fpcalc_override(fpcalc_path: str):
    if fpcalc_path and os.path.isfile(fpcalc_path):
        acoustid.FPCALC_COMMAND = fpcalc_path


def compute_local_fingerprint(filepath: str, fpcalc_path: str = ""):
    """
    Computes a Chromaprint fingerprint locally (no AcoustID API call, no key
    required) for use in duplicate detection. Returns (duration, fingerprint)
    where fingerprint is a string, or (0.0, "") if unavailable.
    """
    _apply_fpcalc_override(fpcalc_path)
    try:
        duration, fp = acoustid.fingerprint_file(filepath)
        if isinstance(fp, bytes):
            fp = fp.decode("utf-8", errors="ignore")
        return duration, fp
    except acoustid.NoBackendError:
        raise FpcalcNotFoundError(
            "fpcalc (Chromaprint) executable not found. Set its path in "
            "Settings or add it to your system PATH. See README."
        )
    except Exception:
        return 0.0, ""


def match_file(filepath: str, api_key: str, fpcalc_path: str = "") -> list:
    """
    Returns a list of (score, recording_id, title, artist) tuples sorted by
    descending score (score is 0.0 - 1.0), or an empty list if no match /
    fingerprinting unavailable.
    """
    if not api_key:
        return []

    _apply_fpcalc_override(fpcalc_path)

    try:
        results = list(acoustid.match(api_key, filepath, parse=True))
        return results
    except acoustid.NoBackendError:
        raise FpcalcNotFoundError(
            "fpcalc (Chromaprint) executable not found. Download it and set "
            "its path in Settings, or add it to your system PATH. See README."
        )
    except acoustid.FingerprintGenerationError:
        return []
    except acoustid.WebServiceError:
        return []
    except Exception:
        return []
