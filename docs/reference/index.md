# API Reference

The pages below are generated from public objects in `src/phmaster/`.

| Module | Purpose |
|--------|---------|
| `phmaster.main` | Initialize logging and run the CLI |
| `phmaster.cli.app` | Register command groups and global options |
| `phmaster.cli.callbacks.meta` | Handle eager metadata options |
| `phmaster.cli.commands.completion` | Install or print shell completion |
| `phmaster.cli.commands.process` | Add normalized tracks to video files |
| `phmaster.cli.commands.probe` | List tracks and measure loudness |
| `phmaster.cli.progress` | Show pipeline progress on stderr |
| `phmaster.cli.context` | Share settings, console, and output format with commands |
| `phmaster.cli.errors` | Report service errors and set exit codes |
| `phmaster.services.errors` | Define expected use-case failures |
| `phmaster.services.normalize` | Process one media file |
| `phmaster.services.batch` | Discover and process several files |
| `phmaster.services.analyze` | Measure tracks and estimate preset gains |
| `phmaster.services.pipeline` | Select tracks, plan jobs, measure and render |
| `phmaster.services.dsp.loudness` | Measure BS.1770 loudness |
| `phmaster.services.dsp.gain` | Plan and apply the gain curve |
| `phmaster.services.dsp.presets` | Define preset parameters |
| `phmaster.services.media.probe` | Read media streams with ffprobe |
| `phmaster.services.media.commands` | Build ffmpeg decode, encode, and mux commands |
| `phmaster.services.media.pcm` | Stream PCM to and from ffmpeg |
| `phmaster.services.media.layouts` | Describe channel layouts |
| `phmaster.services.media.tools` | Locate and run ffmpeg and ffprobe |
| `phmaster.config.settings` | Define and load application settings |
| `phmaster.utils.console` | Configure and share the Rich console |
| `phmaster.utils.log` | Configure console and file logging |
| `phmaster.utils.meta` | Read installed distribution metadata |
| `phmaster.utils.output` | Render text or JSON command output |
| `phmaster.utils.format` | Define the Rich theme |
