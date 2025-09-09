# SubShift Architecture Documentation

## Overview

SubShift is a subtitle synchronization utility that aligns out-of-sync subtitles to edited videos using AI transcripts and Levenshtein distance matching. The application follows a modular pipeline architecture with clear separation of concerns.

## System Architecture

```
Video File → Audio Extraction → AI Transcription → Text Alignment → Offset Calculation → Corrected Subtitles
     ↓              ↓                    ↓               ↓               ↓                    ↓
   FFmpeg      OpenAI/Google     Levenshtein Distance   Linear        Backup Original    Save .srt
  (4 samples)    Whisper API     Similarity Matching   Interpolation   + Apply Offsets
```

## Core Components

### 1. CLI Interface (`src/subshift/cli.py`)
- **SubShiftCLI**: Main command-line interface class
- Argument parsing with argparse
- Environment variable loading (OPENAI_API_KEY, GOOGLE_PLACES_API_KEY)
- Configuration validation
- Error handling and user feedback

**Key Features:**
- Support for both OpenAI and Google Speech-to-Text APIs
- Configurable similarity thresholds and search windows
- Debug mode with verbose logging
- Dry-run capability for testing

### 2. Audio Processing (`src/subshift/audio.py`)
- **AudioProcessor**: Handles video analysis and audio extraction
- **AudioSample**: Data class representing extracted audio segments

**Audio Extraction Strategy:**
- Extract 4 random 1-minute samples by default
- Sample every 5 minutes starting from 5:00 mark
- Maximum 15 samples total for long media
- 16kHz mono PCM format for AI compatibility
- Retry logic for failed extractions

**Duration Estimation:**
- FFprobe for accurate duration detection
- Heuristic fallback: TV shows (20min), Movies (90min)

### 3. AI Transcription (`src/subshift/transcribe.py`)
- **TranscriptionEngine**: Abstract base class for AI engines
- **WhisperEngine**: OpenAI Whisper implementation (primary)
- **GoogleSpeechEngine**: Google Cloud Speech-to-Text (secondary)

**Text Cleaning Pipeline:**
- HTML tag removal (`<b>`, `<i>`, etc.)
- WebVTT styling removal (`<c.color>`)
- Bracketed description removal (`[music]`, `(laughter)`)
- Symbol cleanup (♪, ♫, ★)
- Whitespace normalization

**Retry Logic:**
- Exponential backoff (2^n seconds)
- 3 retry attempts maximum
- API quota handling

### 4. Subtitle Processing (`src/subshift/subtitles.py`)
- **SubtitleProcessor**: SRT parsing and normalization
- **SubtitleEntry**: Data class for subtitle segments

**Features:**
- SRT-only format support (rejects .ass, .sub, .idx, etc.)
- Minute-based text aggregation and indexing
- Character threshold filtering (≥40 chars by default)
- Case-insensitive comparison preparation

**Text Normalization:**
- HTML/WebVTT tag stripping
- Speaker label removal (`NAME:`)
- Sound description removal (`[door slam]`)
- Symbol and emoji cleanup
- Lowercase conversion for comparison

### 5. Alignment Engine (`src/subshift/align.py`)
- **AlignmentEngine**: Core matching algorithm
- **AlignmentMatch**: Data class for match results

**Levenshtein Algorithm:**
- Similarity = 1 - (edit_distance / max_length)
- Default threshold: 70% similarity (configurable)
- Search window: ±20 minutes around audio sample
- Best match selection per sample

**Search Strategy:**
- Chronological and reverse-chronological scanning
- Configurable time window around sample points
- Character count validation (minimum 40 chars)

### 6. Offset Calculation (`src/subshift/offset.py`)
- **OffsetCalculator**: Time correction computation and application

**Offset Calculation:**
```
Offset = subtitle_timestamp - audio_sample_timestamp
Positive = subtitles are ahead (delay needed)
Negative = subtitles are behind (advance needed)
```

**Linear Interpolation:**
- Between successful alignment points
- Smooth transitions across timeline
- Boundary condition handling (start/end of video)

**SRT Modification:**
- Preserves original formatting and text
- Updates only timing information
- Ensures non-negative timestamps
- Maintains minimum subtitle duration

### 7. Backup System (`src/subshift/backup.py`)
- **BackupManager**: Intelligent file retention

**Retention Policies:**
- Files <150KB: Keep up to 50 copies
- Files ≥150KB: Keep up to 25 copies  
- ISO-8601 timestamped backups
- Automatic cleanup of oldest backups

### 8. Logging System (`src/subshift/logging.py`)
- **SubShiftLogger**: Rich-integrated logging

**Features:**
- 5MB log rotation on startup
- Rich console output with colors
- INFO default, DEBUG with --debug flag
- File and console handlers
- Structured error reporting

### 9. Main Controller (`src/subshift/sync.py`)
- **SubtitleSynchronizer**: Orchestrates entire pipeline

**Workflow:**
1. Audio sample extraction
2. AI transcription processing  
3. Subtitle parsing and indexing
4. Text alignment and matching
5. Offset calculation and interpolation
6. Subtitle correction and backup

## Data Flow

### Input Processing
1. **Video Analysis**: Duration detection, sample time generation
2. **Audio Extraction**: FFmpeg-based segment extraction to WAV
3. **AI Processing**: Whisper/Google Speech transcription
4. **Subtitle Parsing**: SRT file parsing with pysrt library

### Alignment Phase
1. **Indexing**: Minute-based subtitle text aggregation
2. **Candidate Search**: Time window-based text matching
3. **Similarity Scoring**: Levenshtein distance calculation
4. **Match Selection**: Best similarity score per sample

### Correction Phase
1. **Offset Calculation**: Per-sample time differences
2. **Interpolation**: Linear offset smoothing
3. **Timeline Application**: SRT timestamp modification
4. **File Operations**: Backup creation and corrected output

## Configuration

All configuration is provided via command-line arguments with environment variable overrides:

### Required Parameters
- `--video`: Input video file path
- `--subs`: Input SRT subtitle file path

### Optional Parameters  
- `--api`: AI engine (openai/google, default: openai)
- `--search-window`: Search radius in minutes (default: 20)
- `--similarity-threshold`: Match threshold 0.0-1.0 (default: 0.7)
- `--min-chars`: Minimum text length for matching (default: 40)
- `--samples`: Number of audio samples (default: 4)
- `--debug`: Enable verbose logging
- `--curses`: Interactive UI mode (future feature)
- `--dry-run`: Analysis without file modification

### Environment Variables
- `OPENAI_API_KEY`: OpenAI Whisper API key
- `GOOGLE_PLACES_API_KEY`: Google Speech-to-Text credentials

## File System Layout

```
subshift/
├── src/subshift/           # Core application modules
│   ├── __init__.py
│   ├── cli.py             # Command-line interface
│   ├── audio.py           # Audio processing
│   ├── transcribe.py      # AI transcription engines  
│   ├── subtitles.py       # SRT parsing and indexing
│   ├── align.py           # Alignment algorithm
│   ├── offset.py          # Offset calculation
│   ├── backup.py          # Backup management
│   ├── logging.py         # Logging system
│   └── sync.py            # Main controller
├── tests/                  # Unit and integration tests
├── docs/                   # Documentation
│   ├── design.md          # Requirements and design
│   └── architecture.md    # This file
├── backup/                 # Subtitle backups (created at runtime)
├── logs/                   # Application logs
├── tmp/                    # Temporary audio files
├── requirements.txt        # Python dependencies
├── README.md              # User documentation
└── .gitignore             # Git ignore rules
```

## Error Handling

### Classification
- **Transient Errors**: Network timeouts, API rate limits
- **Fatal Errors**: Missing files, invalid formats, authentication failures

### Retry Strategy
- 3 attempts with exponential backoff (2^n seconds)
- API quota detection and graceful degradation
- FFmpeg failure handling with detailed logging

### Recovery Mechanisms
- Multiple audio sample extraction attempts
- Alternative sampling locations on failure
- Graceful degradation with partial results

## Performance Considerations

### Memory Management
- Streaming audio processing (no full video loading)
- Temporary file cleanup after processing
- Efficient subtitle indexing with dictionaries

### API Optimization
- Batch audio processing where possible
- Configurable sample count for cost management
- Error handling to avoid API quota exhaustion

### File I/O
- Minimal disk space usage with temporary files
- Intelligent backup retention policies
- SRT streaming for large subtitle files

## Future Enhancements

### Phase 1 (Current Implementation)
- [x] Core synchronization pipeline
- [x] OpenAI Whisper and Google Speech support
- [x] SRT format processing
- [x] Command-line interface

### Phase 2 (Planned)
- [ ] Interactive curses UI with progress tracking
- [ ] Binary subtitle format support (.ass, .sub)
- [ ] SDH description removal with AI
- [ ] Batch processing capabilities

### Phase 3 (Future)
- [ ] Web dashboard interface
- [ ] Media server integration (Plex, Jellyfin)
- [ ] Machine learning-based sync prediction
- [ ] Quality confidence scoring

## Dependencies

### Core Libraries
- **ffmpeg-python**: Video/audio processing
- **python-Levenshtein**: Text similarity calculation  
- **openai**: Whisper API client
- **google-cloud-speech**: Google Speech-to-Text
- **pysrt**: SRT file parsing and generation

### UI and Display
- **rich**: Enhanced console output and logging
- **tqdm**: Progress bars
- **blessed**: Terminal control (curses alternative)

### Utilities
- **python-dotenv**: Environment variable management
- **click**: Command-line utilities
- **requests**: HTTP client for API calls

## Known Limitations

### Format Restrictions
- SRT subtitle files only (no ASS, SUB, VTT support)
- Video formats supported by FFmpeg
- English language optimized (configurable in future)

### API Dependencies
- Requires internet connection for AI transcription
- Subject to API rate limits and costs
- Quality dependent on audio clarity and AI accuracy

### Accuracy Factors
- Video/subtitle sync quality affects results
- Background noise impacts transcription accuracy
- Complex dialogue may reduce matching success

### Performance Constraints
- Processing time scales with video length
- API latency affects total runtime
- Memory usage scales with subtitle file size
