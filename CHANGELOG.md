# Changelog

All notable changes to this project will be documented in this file.

## v0.1.0 (2026-10-13)

### Feat

- **media**: check ffmpeg versions and required encoders early
- **process**: replace generated tracks only on title collision
- add process and probe commands with normalize, batch, and analyze use cases
- **dsp**: add BS.1770 loudness metering and non-causal smooth gain planning with presets
- **media**: add ffprobe probing, PCM decode/encode pipes, and stream-copy muxing

### Fix

- **render**: keep generated tracks under the true-peak ceiling after encoding
- **dsp**: fade the quiet-scene boost out towards the silence threshold
- **dsp**: gate the stereo reference level on the programs speech level
- **pipeline**: choose kept layouts the selected encoder can store
- **normalize**: keep in-place outputs safe for upper-case extensions and existing files
- **log**: fall back to console logging when the log directory is unusable
- **media**: refuse tracks whose channel layout cannot be inferred
- **process**: tie generated tracks to their source track and match the exact title suffix
- **process**: keep source file permissions when replacing in place
- **batch**: skip hidden directories when scanning recursively
- **media**: drop data streams that the output container cannot hold
- **process**: publish without hard links and report filesystem errors per file
- **media**: accept ffmpeg git builds by libavfilter version
- **config**: validate processing values before media work
- **process**: publish outputs without overwriting concurrent files
- **media**: preserve source streams and audio dispositions during mux

### Refactor

- load settings once per process and remove unused template utilities
- **pipeline**: remove unused plan_all and share the PCM sample rate
- **pipeline**: plan audio jobs lazily
