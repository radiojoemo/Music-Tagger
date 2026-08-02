"""
scanner.py
Walks a folder tree and yields paths to supported audio files.
"""

import os

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".wav"}


def scan_folder(root_path: str, recursive: bool = True):
    """
    Yield full file paths under root_path that match supported audio extensions.
    """
    if not os.path.isdir(root_path):
        return

    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root_path):
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in AUDIO_EXTENSIONS:
                    yield os.path.join(dirpath, fname)
    else:
        for fname in os.listdir(root_path):
            full = os.path.join(root_path, fname)
            if os.path.isfile(full) and os.path.splitext(fname)[1].lower() in AUDIO_EXTENSIONS:
                yield full


def count_audio_files(root_path: str, recursive: bool = True) -> int:
    return sum(1 for _ in scan_folder(root_path, recursive))
