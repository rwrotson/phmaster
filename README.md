# phmaster

Watch films at night without waking the neighbours. `phmaster` adds loudness-normalized audio tracks to video files: explosions are tamed, whispers are raised, and the level stays smooth, without pumping, sudden dips, or peaks slipping through. The original tracks are kept, so you can switch back at any time.

- Works with containers and codecs ffmpeg can read; video, audio, subtitles, and attachments are copied bit-identically, data streams are copied only into MOV (Matroska and WebM cannot hold them; MP4 rewrites timecode tracks)
- Plans the gain over the whole track before rendering, so the level eases down just before a loud moment instead of reacting after it
- Measures loudness per ITU-R BS.1770 and anchors it to the dialogue level, using the center channel when there is one
- Presets `light`, `medium`, and `night`; generate several in one run
- Stereo downmix with a dialogue boost for TV and laptop speakers, or keep 5.1 for a soundbar, or both
- AAC for stereo and E-AC-3 for 5.1 by default, which TVs, soundbars, and media servers play without transcoding
- Batch processing of directories, track selection by index or language, Docker image

## Requirements

- [ffmpeg and ffprobe](https://ffmpeg.org/download.html) 6.0 or newer on `PATH`
- Python 3.14+ and [uv](https://docs.astral.sh/uv/), or Docker

The CLI checks tool versions and the required audio encoders before processing media.

## Installation

```bash
uv tool install git+https://github.com/rwrotson/phmaster
```

Or from a clone:

```bash
uv sync --locked
uv run phmaster --help
```

## Usage

```bash
# Inspect the audio tracks (indices a:N are used by --track)
phmaster probe movie.mkv

# Measure loudness and preview the gain each preset would apply
phmaster probe movie.mkv --loudness -p night -p medium

# Write movie.phm.mkv with a night-mode stereo track added and marked as default
phmaster process movie.mkv

# Two presets, stereo and 5.1, Russian tracks only, a whole series recursively
phmaster process ~/Series -r -p night -p medium --layout both --lang rus

# Replace the original file (an .avi becomes .mkv; the old file is removed)
phmaster process movie.avi --in-place

# Show what would be generated
phmaster process ~/Movies --dry-run
```

Files that already contain phmaster tracks, and files whose output exists, are skipped; `--force` processes them anyway. With `--force`, new tracks replace earlier phmaster tracks with the same title. Use `--title` to give new tracks a different title and keep the earlier ones. Outputs of earlier runs (`*.phm.*`) are ignored when scanning directories.

### Options of `process`

| Option | Default | Effect |
|--------|---------|--------|
| `-p, --preset` | `night` | `light`, `medium`, or `night`; repeat for several tracks |
| `-l, --layout` | `stereo` | `stereo` downmix, `keep` the source layout (more than 5.1 becomes 5.1), or `both` |
| `-c, --codec` | `auto` | `auto` (AAC for stereo, E-AC-3 for 5.1), `aac`, `eac3`, `ac3`, `opus`, `flac` |
| `-t, --track` | all | Source audio track index; repeatable |
| `--lang` | all | Source track language code, such as `rus`; repeatable |
| `--center-mix` | `0` | Center (dialogue) level in stereo downmixes, dB; the ITU default is `-3` |
| `-r, --recursive` | off | Search directories recursively |
| `--in-place` | off | Replace the source file instead of writing a copy |
| `--force` | off | Process files with existing phmaster tracks or outputs |
| `--title` | source title | Base title for new tracks; a different title keeps earlier phmaster tracks with `--force` |
| `-n, --dry-run` | off | Show the plan without writing files |
| `--default/--no-default` | `--default` | Mark the first new track as the default audio track |

Global options go before the command: `-V, --verbose` for debug logs, `-f, --output-format json` for machine-readable output on stdout.

### Presets

| Preset | Dialogue level | Loud moments over dialogue | Use |
|--------|----------------|----------------------------|-----|
| `light` | −23 LUFS | gently reduced | evening, keeps the film's dynamics |
| `medium` | −21 LUFS | clearly reduced | quiet room |
| `night` | −20 LUFS | close to dialogue | neighbours asleep |

How the gain is planned: [Algorithm](https://rwrotson.github.io/phmaster/algorithm/).

## Docker

```bash
docker build -t phmaster .
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/media" phmaster process movie.mkv
```

The container works in `/media`; pass paths relative to the mounted directory.

## Configuration

Defaults can be changed with `PHMASTER_*` environment variables or a `.env` file in the working directory; command-line options win. Sections are nested with `__`:

| Prefix | Controls |
|--------|----------|
| `PHMASTER_PROCESSING__*` | Default presets, layout, codec, bitrates, languages, output suffix, ffmpeg paths |
| `PHMASTER_CONSOLE__*` | Rich console (width, colors, quiet mode) |
| `PHMASTER_LOG__*` | Log levels, renderer, log directory, file rotation |

```env
PHMASTER_PROCESSING__PRESETS=["night","medium"]
PHMASTER_PROCESSING__LAYOUT=both
PHMASTER_PROCESSING__LANGUAGES=["rus","eng"]
```

See `.env.example` for every setting.
Bitrates must be positive numbers with an optional `k` or `M` suffix, the output suffix must be a filename fragment, and the center mix must be between −12 and +12 dB.

## Development

```bash
uv sync --all-groups --locked
uv run pre-commit install

uv run poe check       # format check, lint, import contracts, strict mypy, tests with coverage
uv run poe test-fast   # tests without coverage
uv run pytest tests/services/test_normalize.py
uv run poe docs        # documentation site with live reload
```

Tests generate short media files with ffmpeg, so ffmpeg must be installed. Architecture, conventions, and CI are described in `AGENTS.md` and on the [Architecture](https://rwrotson.github.io/phmaster/architecture/) page.

## Author

Igor Lashkov — rwrotson@yandex.ru
