# SubShift 🎯

AI-powered subtitle synchronization utility that aligns out-of-sync subtitles to edited videos using speech transcription and Levenshtein distance matching.

## ✨ Features

- **🤖 AI Transcription**: OpenAI Whisper (primary) + Google Speech-to-Text
- **🎯 Smart Sampling**: Extract 4 random 1-minute audio samples for analysis
- **📊 Levenshtein Matching**: 70% similarity threshold with ±20 minute search windows
- **🔄 Linear Interpolation**: Progressive offset correction across timeline
- **🧹 SDH Removal**: AI-powered Sound Description removal (optional, ~$0.002 per 100KB)
- **🔐 Secure**: Environment variable API key loading
- **📝 Logging**: 5MB rotation, Rich color output, debug mode
- **💾 Backup**: Intelligent retention (50 copies <150KB, 25 copies ≥150KB)
- **⚡ Retry Logic**: Exponential backoff with error classification

## 🚀 Quickstart

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set API key
export OPENAI_API_KEY="your_api_key_here"

# Basic sync
subshift --media movie.mp4 --sub movie.srt

# Advanced sync with SDH removal
subshift --media show.mkv --sub show.srt --remove-sdh --debug
```

## 📖 Usage Examples

### Basic Synchronization
```bash
# Standard sync with OpenAI Whisper
subshift --media movie.mp4 --sub movie.srt

# Use Google Speech-to-Text instead
subshift --media movie.mp4 --sub movie.srt --api google

# Adjust similarity threshold (more/less strict)
subshift --media movie.mp4 --sub movie.srt --similarity-threshold 0.8
```

### Advanced Options
```bash
# Larger search window for heavily edited content
subshift --media movie.mp4 --sub movie.srt --search-window 30

# Debug mode with detailed comparison output
subshift --media movie.mp4 --sub movie.srt --debug

# Interactive curses UI with live progress
subshift --media movie.mp4 --sub movie.srt --curses

# Dry run (analysis only, no file changes)
subshift --media movie.mp4 --sub movie.srt --dry-run
```

### SDH (Sound Description) Removal
```bash
# Estimate cost for SDH removal
subshift --sub movie.srt --sdh-cost-estimate

# Remove SDH with AI analysis (requires API key)
subshift --media movie.mp4 --sub movie.srt --remove-sdh

# Combined sync + SDH removal
subshift --media movie.mp4 --sub movie.srt --remove-sdh --debug
```

### 💰 Cost Analysis (SDH Removal)

For average **100KB subtitle file**:
- ~2000 lines → ~500 AI analysis chunks
- ~10K tokens estimated
- **Cost: ~$0.002 USD** (less than 1 cent)
- Uses OpenAI GPT-4 Mini pricing

**SDH removal is configurable and OFF by default.**

## 🛠️ Configuration

### Environment Variables
```bash
# OpenAI Whisper (primary)
export OPENAI_API_KEY="sk-proj-..."

# Google Speech-to-Text (secondary) 
export GOOGLE_PLACES_API_KEY="AIza..."
```

### Command Line Options
```
Required:
  --video, -v       Path to video file (.mp4, .mkv, .avi, etc.)
  --subs, -s        Path to subtitle file (.srt format only)

Optional:
  --api             AI engine: openai (default) or google
  --samples         Number of audio samples (default: 4)
  --search-window   Search radius in minutes (default: 20)
  --similarity-threshold  Match threshold 0.0-1.0 (default: 0.7)
  --min-chars       Minimum text length for matching (default: 40)
  --remove-sdh      Remove Sound Descriptions (default: off)
  --sdh-cost-estimate  Show SDH removal cost estimate
  --debug           Enable verbose logging
  --curses          Interactive UI mode (future feature)
  --dry-run         Analysis without file modification
```

## 🔧 How It Works

1. **Audio Extraction**: Extract 4 random 1-minute samples using FFmpeg
2. **AI Transcription**: Convert audio to text using Whisper/Google Speech
3. **Subtitle Parsing**: Parse SRT file into minute-based text index
4. **Text Alignment**: Match AI transcripts with subtitle text using Levenshtein distance
5. **Offset Calculation**: Calculate time corrections from successful matches
6. **Linear Interpolation**: Apply smooth corrections across timeline
7. **File Output**: Save corrected SRT with original backup
8. **SDH Removal** (optional): AI-powered removal of sound descriptions

## 📁 Output Files

```
original.srt              # Your original subtitle file
original.corrected.srt    # Time-synchronized version
original.no-sdh.srt       # SDH-cleaned version (if --remove-sdh)
backup/
  └── original.2025-09-09T10-30-45.srt  # Timestamped backup
```

## 🧪 Algorithm Details

- **Sampling Strategy**: Every 5 minutes starting at 5:00, max 15 samples
- **Audio Format**: 16kHz mono PCM WAV for AI compatibility
- **Similarity Calculation**: `1 - (levenshtein_distance / max_length)`
- **Match Threshold**: ≥70% similarity + ≥40 character minimum
- **Search Window**: ±20 minutes around each audio sample
- **Interpolation**: Linear between successful match points
- **Error Handling**: 3 retries with exponential backoff + jitter

## 🔍 Design & Architecture
See `docs/design.md` and `docs/architecture.md`

## TODO (Future Work)
- Strip SDH descriptions with AI
- Binary subtitle support (.ass, .sub, etc)
- Batch processing for multiple files
- Web dashboard interface
- Media server integration (Plex, Jellyfin)

## Related
- gridshift: https://github.com/mcollard0/gridshift - Automated media download manager

