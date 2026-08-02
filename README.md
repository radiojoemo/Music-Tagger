# Music Tagger

A Windows desktop app that scans a folder of audio files and automatically
fixes their tags — artist, title, album, genre, label, ISRC, and cover art —
by identifying each track against MusicBrainz and Discogs. It also keeps a
searchable library of everything it's tagged, finds duplicate tracks, and
lets you undo an entire tagging run if something looks wrong.

Supports MP3, FLAC, M4A/AAC (and best-effort OGG/WMA/WAV).

**Contents**
- [What you'll need](#what-youll-need)
- [Setup](#setup)
- [Running it](#running-it)
- [The three tabs](#the-three-tabs)
- [How matching works](#how-matching-works)
- [Junk metadata protection](#junk-metadata-protection)
- [Album art](#album-art)
- [ISRC support](#isrc-support)
- [Troubleshooting](#troubleshooting)
- [Extending it](#extending-it)

## What you'll need

- **Python 3.10+** on Windows
- A free **AcoustID API key** (for audio fingerprinting — the most accurate
  matching method)
- A free **Discogs personal access token** (used as a fallback source)
- Optionally, **Chromaprint (`fpcalc.exe`)** — without it, fingerprinting is
  skipped and the app falls back to text-based matching only, which still
  works but is less accurate

All four are covered step by step below.

## Setup

### 1. Install Python dependencies

Open Command Prompt in the project folder and run:

```
pip install -r requirements.txt
```

Using a virtual environment is optional but tidy:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Chromaprint (`fpcalc`) — recommended, not required

This enables acoustic fingerprinting, which identifies a track from the
audio itself rather than relying on existing tags or the filename.

1. Go to https://acoustid.org/chromaprint
2. Download the Windows build (`chromaprint-fpcalc-*-windows-x86_64.zip`)
3. Unzip it somewhere permanent, e.g. `C:\Tools\chromaprint\fpcalc.exe`
4. You'll point the app at this file directly in Settings (step 5 below) —
   no need to touch your system PATH

### 3. Get an AcoustID API key (free)

1. Go to https://acoustid.org/api-key and log in (or create an account)
2. Fill in the short form to register an "application" — any name works,
   e.g. "My Music Tagger"
3. Copy the API key it gives you

### 4. Get a Discogs personal access token (free)

1. Create a free account at https://www.discogs.com if needed
2. Go to https://www.discogs.com/settings/developers
3. Click **Generate new token** and copy it

Discogs is used as a fallback when MusicBrainz doesn't have a confident
match — it's particularly useful for vinyl-only pressings, remixes, and
electronic/DJ tracks that MusicBrainz sometimes lacks.

### 5. Enter your keys in the app

Once you've launched the app (next section), go to **Tools → Settings** and
fill in:
- AcoustID API key
- Discogs token
- fpcalc.exe path (browse to wherever you unzipped it)

Click **Save**. These are stored locally in
`%APPDATA%\MusicTagger\config.json` and persist between runs.

## Running it

```
python main.py
```

1. Go to the **Tag Files** tab
2. Click **Select Folder…** and choose your music folder (scans recursively)
3. Click **Start Scan & Tag**
4. Watch the table update live — matched files get tagged automatically
   once confidence is above your threshold (default 85%, adjustable in
   Settings)
5. Anything below that threshold lands in the **Review Queue** button —
   click it once the scan finishes to go through those files one by one,
   edit fields if needed, and accept or skip each one

## The three tabs

- **Tag Files** — the scan/match/tag workflow described above
- **Library** — every file the app has ever scanned, in a searchable table
  (backed by a local SQLite database at `%APPDATA%\MusicTagger\library.db`).
  Search by artist/title/album/path, see library-wide stats, jump to a
  file's folder, or remove an entry from the index (this doesn't delete the
  actual file)
- **Duplicates** — scans your *entire* library (not just the last folder)
  for likely duplicate tracks, using three signals in order of reliability:
  1. Identical audio fingerprint (same audio content, even with completely
     different tags) — computed locally, no AcoustID key needed
  2. Same MusicBrainz recording ID
  3. Fuzzy artist/title match with duration proximity, as a fallback

  Select specific files within a duplicate group and click **Delete
  Selected Files…** — this permanently deletes them from disk (with a
  confirmation prompt first), not just from the library index.

There's also **Tools → History / Undo**: every tagging run is logged as a
batch with each file's before/after tags. Pick a past batch and click
**Undo Selected Batch** to restore every file in that run to its previous
tags in one action.

> Note: the fuzzy-match pass in Duplicates is O(n²) across your library, so
> on very large collections (tens of thousands of tracks) it may take a
> moment. The fingerprint and MusicBrainz-ID passes stay fast regardless of
> library size.

## How matching works

1. **Acoustic fingerprint** (if AcoustID key + fpcalc are set up) — the
   audio itself is fingerprinted and looked up via AcoustID, which returns
   a MusicBrainz recording ID. This is the most reliable method since it
   doesn't depend on existing tags or filename accuracy at all.
2. **MusicBrainz text search** (fallback) — uses existing artist/title
   tags, or guesses them from the filename (`Artist - Title.mp3` pattern)
   if tags are empty.
3. **Discogs text search** (final fallback) — used when MusicBrainz doesn't
   return a confident match.

Confidence combines the fingerprint match score (when available) with
fuzzy text similarity between your existing artist/title and the candidate
match. You control the auto-write cutoff in Settings — anything below it
goes to the Review Queue instead of being written automatically.

## Junk metadata protection

Plenty of files floating around the internet have junk stuffed into their
label, catalog number, genre, or even ISRC fields — most commonly a
scene-release or download-site name (e.g. "PMEDIA") planted by whatever
tool ripped or shared the file. The app takes a zero-trust approach to
this:

1. **Writing** — when the app tags a file, it fully replaces the
   label/catalog/genre/ISRC/MusicBrainz-ID fields with whatever the match
   provided (even if that's blank), instead of leaving old values in place
   underneath the new ones.
2. **Displaying** — a file that hasn't actually been matched against
   MusicBrainz/Discogs never shows its raw label/catalog/genre/ISRC/
   MusicBrainz-ID fields in the Library — those only ever come from a
   confirmed match. Artist, title, and album are still shown from the
   file itself, since those aren't a typical junk-injection target and
   are needed to search for a match in the first place.

If your library already has junk from before this fix, the **Library**
tab has two cleanup tools at the bottom:

- **Sanitize All Unmatched Tracks** (recommended) — blanks label, catalog
  #, genre, ISRC, and MusicBrainz IDs on every track that's never actually
  been matched, regardless of what specific junk value is sitting there.
  This is the "assume it's flawed unless proven otherwise" option, so you
  don't need to know every possible junk value in advance.
- **Clear junk value across library** — clears one *specific* known value
  (e.g. `PMEDIA`) from those same fields, wherever it appears — useful if
  you want to target a value on tracks that otherwise do have a real match.

Both only touch the library index, not the actual files — re-scanning a
file will refresh it from MusicBrainz/Discogs as usual.

## Album art

When a match is found (auto-written or accepted from the Review Queue),
the app downloads and embeds the front cover:

1. **Cover Art Archive** (linked to the matched MusicBrainz release) —
   tried first, free, no API key needed
2. **Discogs release images** — fallback when MusicBrainz has no art for
   that release, or when the match came from Discogs

Art is embedded directly in the file (an `APIC` frame for MP3, an embedded
picture for FLAC, a `covr` atom for M4A). Toggle this off in **Tools →
Settings** if you'd rather leave existing artwork alone or skip the extra
downloads.

## ISRC support

Every track also gets tagged with its ISRC (International Standard
Recording Code):

- **MP3** — stored in the standard `TSRC` ID3 frame
- **FLAC** — stored as a plain `ISRC` Vorbis comment
- **M4A/AAC** — stored as a freeform atom (there's no dedicated MP4 atom
  for it)
- Pulled from **MusicBrainz**'s recording data when a match is found;
  Discogs only supplies it occasionally (it's not a first-class field
  there), so it's best-effort for Discogs-sourced matches

It's editable in the Review dialog and searchable/sortable as a column in
the Library tab.

## Troubleshooting

**`'python' is not recognized...`**
Python isn't installed or isn't on PATH. Reinstall from
https://www.python.org/downloads/ and check "Add python.exe to PATH" during
setup.

**`Bad includes: ... is not a valid include` in the log**
This was a bug in earlier versions where a MusicBrainz API call requested
a field the installed library version didn't support. Make sure you're on
the latest version of this project — it's fixed there.

**Seeing "PMEDIA" or other junk in the Label/Genre/ISRC columns**
This was a bug in earlier versions — those fields could leak straight from
the file's existing tags instead of only coming from a real match. Use
**Sanitize All Unmatched Tracks** at the bottom of the Library tab to fix
it retroactively in one click (see
[Junk metadata protection](#junk-metadata-protection)); newer scans won't
reintroduce it.

**No genre/label showing up on a match**
Not every MusicBrainz release has genre or label data submitted by its
contributors — this is a community database, so coverage varies. If
Discogs has it and MusicBrainz doesn't, the Discogs fallback should pick
it up; if neither has it, the field will stay blank for you to fill in
manually via the Review Queue.

**Fingerprinting seems to be skipped / everything goes through text search**
Check that `fpcalc.exe` is either on your system PATH or its full path is
set correctly in **Tools → Settings**. Without it, the app still works
fine — it just relies on text search instead of audio fingerprinting.

**The app doesn't touch my file at all ("No match")**
The track wasn't found on either MusicBrainz or Discogs with enough
confidence, and (if fingerprinting isn't set up) the filename/tags weren't
enough to search from. It's still logged in the Library tab so you can
track what was scanned.

## Extending it

The codebase is split by responsibility so it's easy to grow one piece at
a time:

- `core/scanner.py` — file discovery (add more extensions here)
- `core/tagger.py` — reading/writing tags per format (add new formats here)
- `core/musicbrainz_client.py` / `core/discogs_client.py` — one file per
  metadata source; add a new source by writing a similar module and wiring
  it into `core/matcher.py`
- `core/matcher.py` — the matching/confidence pipeline
- `core/fingerprint.py` — Chromaprint/AcoustID integration (both the
  API-based match and the local-only fingerprint used for duplicate
  detection)
- `core/coverart.py` — cover art fetching
- `core/database.py` — SQLite library + tag-change history
- `core/duplicates.py` — duplicate-detection signals
- `ui/` — all PySide6 windows, tabs, and dialogs

Ideas for next steps: cover art thumbnails in the Library grid, exporting
the library to CSV, and a "merge duplicate metadata" option that combines
the best fields from each copy before deleting the rest.
