# Algorithm

phmaster renders each new track in two passes over the decoded audio. The first pass measures loudness; between the passes the whole gain curve is planned at once, so it can look ahead in time; the second pass applies the curve and encodes the result.

```
pass 1   ffmpeg decode → f32 PCM 48 kHz → K-weighting → block power (10 ms)
plan     reference level → slow gain + compressor → lookahead and release smoothing
pass 2   ffmpeg decode → PCM × gain → ffmpeg: 4× oversampled true-peak limiter → encoder
mux      ffmpeg -c copy: source streams + new tracks (data streams kept only in MOV; fails if the output container rejects another stream)
```

Audio is streamed in one-second chunks. The envelope and gain curve grow with the track length, but processing one track and layout at a time avoids retaining plans for all output tracks.

## Decoding and downmix

Each track is decoded in its target layout. A stereo downmix uses ffmpeg's rematrixing with the center channel at 0 dB instead of the ITU −3 dB (`--center-mix`), surrounds at −3 dB, and no LFE, so dialogue stays intelligible on small speakers. Layouts with more than 5.1 channels are folded into 5.1 when the source layout is kept. A kept layout the encoder cannot store with a standard channel order is converted too: side channels become back channels where that suffices (AAC and Opus), otherwise the track becomes 5.1, so that libopus does not reject it and AAC does not write an unknown layout. A stream without a known layout is assumed to be mono, stereo, 5.1, or 7.1 for 1, 2, 6, or 8 channels; other channel counts are ambiguous (three channels may be 2.1 or 3.0), so such a track is refused before processing rather than risk dropping a channel.

When a stereo downmix loses the source center channel, the decoder appends it as an extra channel that is measured but not encoded.

## Loudness measurement

Loudness follows ITU-R BS.1770-4: a K-weighting filter (high shelf and high-pass), mean-square power per channel, channel weights of 1.41 for surrounds and 0 for LFE. Power is kept per 10 ms block; momentary (400 ms) and short-term (3 s) loudness are moving averages of it.

## Reference level

The reference is the dialogue level that the preset target applies to:

1. Blocks below −70 LUFS, and blocks 20 LU below the median, are ignored.
2. With a center channel, dialogue is active where the center is within 10 LU of its speech level (the 80th percentile of its loudness). The reference is the median program loudness while dialogue is active.
3. Otherwise the reference is the median program loudness.

The median is used instead of the energy mean of integrated loudness, because a few seconds of explosions would otherwise pull the reference up and leave every quiet scene too quiet.

The static gain moves the reference to the preset target.

## Slow gain

The slow gain follows sustained level changes, like a hand on a fader:

- Momentary loudness is computed, silent stretches (below −60 LUFS or 35 LU under the reference) are bridged by interpolation, so pauses and room tone are never raised.
- The running median over 8 seconds gives the scene level. Events shorter than about 4 seconds, in either direction, do not move it; they are left to the compressor.
- The gain is `static gain + strength × (reference − scene level)`, limited by `max_boost` and `max_cut`, and smoothed with a Gaussian.

## Compressor

On top of the slow gain, momentary loudness above `target + threshold` is reduced with the preset ratio and a soft knee.

## Lookahead and release

Because the curve is planned offline, every reduction is reached before the loud moment:

1. A forward minimum holds each dip over the preceding `lookahead` window.
2. A one-pole filter run backwards in time lowers the gain gradually before the dip.
3. A one-pole filter run forwards lets the gain recover after it with the `release` time constant.

Steps 1 and 2 only lower the curve, so the gain at a loud moment never exceeds what the moment needs. The curve is interpolated in dB from 10 ms blocks to individual samples.

## Safety limiter

The encoder runs ffmpeg's `alimiter` at 192 kHz (4× oversampling, so inter-sample peaks are caught) with the preset ceiling in dBTP and delay compensation. It only acts on rare peaks the gain curve leaves; for normal content it is transparent.

## Presets

| | light | medium | night |
|---|---|---|---|
| Dialogue target | −23 LUFS | −21 LUFS | −20 LUFS |
| Strength | 0.5 | 0.75 | 0.9 |
| Max boost / cut | +6 / −6 dB | +9 / −10 dB | +12 / −15 dB |
| Threshold / ratio | +8 LU, 2:1 | +5 LU, 3:1 | +2 LU, 6:1 |
| Knee | 4 dB | 4 dB | 3 dB |
| Lookahead | 0.15 s | 0.2 s | 0.25 s |
| Release | 0.6 s | 0.8 s | 1.0 s |
| Slow gain smoothing (σ) | 1.5 s | 1.5 s | 1.0 s |
| True-peak ceiling | −1 dBTP | −1.5 dBTP | −2 dBTP |

The values live in `phmaster.services.dsp.presets.PRESETS`. With `night`, a scene 20 LU louder than the dialogue comes out about 5 LU louder, and the dialogue after it returns to the target within about two seconds.
