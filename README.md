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

## Related
- gridshift: https://github.com/USERNAME/gridshift

