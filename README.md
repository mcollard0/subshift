# SubShift

Subtitle synchronization utility that aligns out-of-sync subtitles to edited videos using AI transcripts and Levenshtein-based matching.

- Primary ASR: OpenAI Whisper
- Secondary ASR: Google Cloud Speech-to-Text (aka "Google Places Speech to Text" per request)
- CLI-first, env overrides for secrets
- Logging enabled by default, truncates/rotates if >5MB on start
- Backups original subtitles before modifications
- Outputs corrected SRT

## Quickstart

```bash
python3 -m venv venv ; source venv/bin/activate ; pip install -r requirements.txt
subshift --video path/to/video.mp4 --subs path/to/subs.srt
```

## Design
See docs/design.md

## TODO (Future Work)
- Strip SDH descriptions with AI
- Binary subtitle support (.ass, .sub, etc)
- Batch processing for multiple files
- Web dashboard interface
- Media server integration (Plex, Jellyfin)

## Related
- gridshift: https://github.com/mcollard0/gridshift - Automated media download manager

