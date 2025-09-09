# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Initial setup
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Development dependencies ( for testing and linting )
pip install -e .[dev]
```

### Core Usage Commands
```bash
# Basic subtitle sync
PYTHONPATH=src python3 -m subshift.cli --media video.mp4 --sub subtitles.srt

# Development/testing mode with debug output
PYTHONPATH=src python3 -m subshift.cli --media video.mp4 --sub subtitles.srt --debug --dry-run

# SDH removal with cost estimation
PYTHONPATH=src python3 -m subshift.cli --sub subtitles.srt --sdh-cost-estimate
PYTHONPATH=src python3 -m subshift.cli --media video.mp4 --sub subtitles.srt --remove-sdh --debug

# Alternative AI engines
PYTHONPATH=src python3 -m subshift.cli --media video.mp4 --sub subtitles.srt --api google

# Custom parameters for difficult sync cases
PYTHONPATH=src python3 -m subshift.cli --media video.mp4 --sub subtitles.srt --search-window 30 --similarity-threshold 0.6
```

### Testing Commands
```bash
# Run all tests
python3 -m pytest

# Run specific test file
python3 -m pytest tests/test_cli.py
python3 -m pytest tests/test_sdh.py

# Run with coverage report
python3 -m pytest --cov=src/subshift --cov-report=html

# Run tests with debug output
python3 -m pytest -v -s tests/test_cli.py::TestSubShiftCLI::test_argument_parsing_valid
```

### Code Quality Commands
```bash
# Format code ( using user's style preferences )
python3 -m black --line-length 120 src/ tests/

# Lint code
python3 -m flake8 src/ tests/

# Type checking
python3 -m mypy src/subshift/
```

## Architecture Overview

### Pipeline Architecture
SubShift implements a 6-stage pipeline for subtitle synchronization:

1. **Audio Extraction** (`AudioProcessor`) → Extract 4 random 1-minute samples from video using FFmpeg
2. **AI Transcription** (`TranscriptionEngine`) → Convert audio to text using OpenAI Whisper or Google Speech
3. **Subtitle Parsing** (`SubtitleProcessor`) → Parse SRT files and create minute-based text indexes
4. **Text Alignment** (`AlignmentEngine`) → Match AI transcripts to subtitle text using Levenshtein distance
5. **Offset Calculation** (`OffsetCalculator`) → Calculate time corrections and apply linear interpolation
6. **File Correction** (`SubtitleSynchronizer`) → Apply corrections to SRT file with intelligent backup

### Core Module Relationships
```
SubtitleSynchronizer (main controller)
├── AudioProcessor → extracts samples, manages FFmpeg interactions
├── TranscriptionEngine → WhisperEngine | GoogleSpeechEngine
├── SubtitleProcessor → parses SRT, creates minute indexes, validates text
├── AlignmentEngine → Levenshtein matching, similarity scoring, search windows
├── OffsetCalculator → time correction math, linear interpolation, SRT modification  
├── SDHRemover → pattern-based + AI-powered sound description removal
├── BackupManager → intelligent retention policies ( 50 copies <150KB, 25 copies ≥150KB )
└── SubShiftLogger → Rich console output, 5MB rotation, debug modes
```

### Data Flow Pipeline
```
Video File → AudioSample objects → AI transcription text → AlignmentMatch objects → time offsets → corrected SRT
```

**Key Data Structures:**
- `AudioSample`: Contains start_time, duration, file_path, transcription
- `SubtitleEntry`: Contains start_time, end_time, text, minute_index
- `AlignmentMatch`: Contains sample, similarity_score, subtitle_minute, matched_text
- `OffsetPoint`: Contains time, offset_seconds for interpolation

### AI Engine Architecture
The transcription system uses a pluggable engine pattern:
- `WhisperEngine` ( primary ): OpenAI Whisper API with exponential backoff retry
- `GoogleSpeechEngine` ( secondary ): Google Cloud Speech-to-Text
- Both engines implement common `TranscriptionEngine` interface
- Text cleaning pipeline removes HTML tags, WebVTT styling, bracketed descriptions

## Configuration & Environment

### Required API Keys
```bash
# OpenAI Whisper ( primary engine )
export OPENAI_API_KEY="sk-proj-..."

# Google Speech-to-Text ( secondary engine )
export GOOGLE_PLACES_API_KEY="AIza..."

# Optional: Load from .env file
echo "OPENAI_API_KEY=sk-proj-..." > .env
```

### System Dependencies
- **FFmpeg**: Required for audio extraction and processing
- **Python 3.9+**: Core runtime requirement
- **Internet connection**: Required for AI transcription APIs

### Configuration Parameters
- `--search-window`: Time window for subtitle matching ( default: 20 minutes )
- `--similarity-threshold`: Levenshtein match threshold ( default: 0.7 = 70% )
- `--min-chars`: Minimum character count for valid matches ( default: 40 )
- `--samples`: Number of audio samples to extract ( default: 4 )

### File Structure & Outputs
```
project_directory/
├── original.srt                    # Input subtitle file
├── original.corrected.srt          # Time-synchronized output
├── original.no-sdh.srt            # SDH-cleaned output ( if --remove-sdh )
├── backup/
│   └── original.2025-09-09T10-30-45.srt  # Timestamped backup
├── tmp/                            # Temporary audio files ( auto-cleaned )
└── logs/
    └── subshift.log               # Application logs ( 5MB rotation )
```

## SDH ( Sound Description for Hearing Impaired ) Removal

### What Gets Removed
SDH content includes non-dialogue audio descriptions:
- Sound effects: `[door slam]`, `(phone ringing)`, `*explosion*`
- Music descriptions: `♪ theme song ♪`, `[upbeat music]`, `<applause>`
- Speaker labels: `NARRATOR:`, `JOHN:`, `VOICE OVER:`

### Detection Algorithm
1. **Pattern-based filtering**: Regex patterns for obvious SDH markers
2. **AI analysis** ( optional ): OpenAI GPT-4 Mini for ambiguous cases
3. **Heuristic validation**: Keyword matching for sound/music terminology

### Cost Estimation
```bash
# Estimate SDH removal cost before processing
PYTHONPATH=src python3 -m subshift.cli --sub movie.srt --sdh-cost-estimate

# Typical costs for 100KB subtitle file:
# ~2000 lines → ~500 AI analysis chunks → ~10K tokens → ~$0.002 USD
```

## Testing & Debugging

### Test Organization
- `tests/test_cli.py`: Command-line interface validation, argument parsing
- `tests/test_sdh.py`: SDH removal functionality, pattern matching, cost estimation
- Test coverage focuses on core algorithm logic and error handling

### Running Specific Tests
```bash
# Test CLI argument validation
python3 -m pytest tests/test_cli.py::TestSubShiftCLI::test_similarity_threshold_validation

# Test SDH pattern recognition
python3 -m pytest tests/test_sdh.py::TestSDHPatterns::test_music_patterns

# Test environment variable loading
python3 -m pytest tests/test_cli.py::TestEnvironmentLoading::test_environment_variable_loading
```

### Debug Workflow
```bash
# Enable debug logging
PYTHONPATH=src python3 -m subshift.cli --media video.mp4 --sub subtitles.srt --debug

# Dry-run mode ( analysis without file modification )
PYTHONPATH=src python3 -m subshift.cli --media video.mp4 --sub subtitles.srt --debug --dry-run

# Check log files
tail -f logs/subshift.log
```

### Common Troubleshooting
- **No audio samples extracted**: Check FFmpeg installation, video file format
- **API transcription failures**: Verify API keys, check internet connection, review API quotas
- **Poor alignment results**: Lower similarity threshold, increase search window, verify video/subtitle sync quality
- **SDH removal too aggressive**: Use pattern-only mode, review AI analysis prompts

### Performance Considerations
- Processing time scales with video length and number of audio samples
- Memory usage scales with subtitle file size and audio sample count
- API latency affects total runtime ( typically 30-120 seconds per sample )
- Temporary audio files require ~4MB disk space per sample

## Integration Notes

This tool integrates with the broader "gridshift" ecosystem for automated media management. The alignment algorithm uses Levenshtein distance with configurable similarity thresholds, making it suitable for heavily edited content where traditional timestamp-based sync fails.

The backup system follows intelligent retention policies ( 50 copies for files <150KB, 25 copies ≥150KB ) to prevent disk space issues during iterative development and testing.

