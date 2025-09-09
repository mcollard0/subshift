# SubShift Design Document

## Original Requirements

Ok, implement a subtitle sync system and test case. This will help correct audio subtitles which are not syncronized to the time of the video, due to edits ("cuts") to the video. 

The requirements are as follows: 
0. Command line arguments should be used (although can be overridden by env keys for passwords and other shared secrets) over a config file or database config table. Logging should be available, on by default, truncated when over 5MB in a check at start time.
1. Subtitle sync is a standalone python project.
2. It supports OAI Whisper (primary, default) and also Google Places Speech to Text.
3. The (AI) API keys are loaded (see GOOGLE_PLACES_API_KEY in ~/.bashrc, assuming OAI is similar)
4. Random quantity 4 audio of duration 1 (min) is extracted in a format (or converted) AI can accept, given the length of the media. If cannot determine length easily, use 20 minutes for TV, and 90 minutes for movies. Attempt to get four one minute samples at random. If one fails, try once on another random number 
5. Audio samples are converted using AI to text, instruct AI to remove styling such as HTML, WebVtt-Style blocks and so on. A list of n samples should be stored, list of maps. Values should be text from subtitle, text from AI Audio parse, Levenshtein (Lev.) distance, time index of first subtitle line, time index of AI audio minute (index of list, example 5 (for 5:00) for the fifth minute of audio.) This will allow for offfset subtraction later.
6. A configuration search duration should be used. Default 20. From the point of the sample (example: sample begins at 5:00 minutes into video, for one minute. 5-6 minute mark) the subtitle text isearched forward and back. Time increments from 5 (start time of sample clip)-20 minutes ( minimum value is 0, do not allow negatives, is int_sub_start_time_min = int_clip_start_time_min - int_config_search_min ) if int_clip_start_time_min - int_config_search_min>0 else 0; Once sub file is dumped (can we process binary subtitles?), iterate as follows: a list is built with the text of subtitle file with the index being the minute number (a full minute) and the value being all the text present in tht minute.
7. Using a loop, loop through the AUDIO sample AI conversion. Processing each minute from the capture start time in both cronological and reverse-cronological order (min:0, max:length of the video duration obtained by the count of listSubtitlesByMin ), compare the text minute by minute. Output comparisons to the screen. Use Levenshtien distance (or similar) to compute similarity. Determine it is a match if there are enough characters to be accurate (say at least 40 (configurable); do subtitle to list first, only select the random minute sample if the subtitle of that list determined by index minute has at least 40 characters) usign a similarity score with a configurable value of percent confidence as defined as 100-{configLevenshteinValueMissedCharsPercent}. So an example, customer says 95(divide by 100) or 95%(drop percent and divide by 100) or 0.95. CAlc is length * percentage. So if user has 100 character subtitle minute, and the percent is 30%, 30 characters is the pass/fall threshold for a match of that minute with less than or equal to is a pass, and greater than is a fail. Once the time of the subtitle text is determined by this method the difference between the time index for the audio clip as determined by the index of the list, and the time index of the subtitle entry. May need to alter structure of said list to a list of minutes [1]->list->tuples with the tuple being time index of the subtitle line, and the actual text.
8. I believe Py starts indexes at one. May need to offset by negative one, as movies/tv start at (0:00) zero minute, not one minute. When debug mode is true (bool_Debug global) print the AI transcribed minute and the subtitle minute to screen for visual comparison and debugging. Show matching value by Lev distance clearly, bold if possible (curses?). If using curses, show status bar on bottom with percentage of completion, number of samples, running time and so forth. 
9. Finally, the subtitle file should be backed up, and the file entries should be parsed using the offsets from each measurement. So for example, for measurements at 5, 10 and 15 minutes in, where the offsets are 5=>1 minute later, 10=-1 minute (earlier), an' 15 is 0:30 seconds (later), for minutes 0-5, add 1 min from the subtitle show time while subtitle file is being processed. For minutes 6-10 subtract 1 min, and 11-15 add thirty seconds. Save this subtitle file, preferring srt format.
10. Suggest changes which will help this to work better.  
11. Save this entire message to a file on disk called "design.md"
12. Update gridshift (readme.md) to reference subshift and give url. And update readme.md in subshift to reference gridshift and show url. Mark gridshift as public repo. Note date and time of making it public and put in the gridshift readme.md (20250909 - Made gridshift public repo (noisemaker emoji))

## Implementation Plan

### Core Architecture

SubShift follows a modular architecture with these key components:

1. **CLI Entry Point** (`src/subshift/cli.py`)
   - Argument parsing for video file, subtitle file, options
   - Environment variable loading for API keys
   - Debug mode toggle
   
2. **Audio Processing** (`src/subshift/audio.py`)
   - FFmpeg wrapper for audio extraction
   - Random sampling strategy (4 samples, 1 minute each)
   - Format conversion for AI compatibility
   
3. **Transcription Engines** (`src/subshift/transcribe.py`)
   - Abstract base class for transcription engines
   - WhisperEngine (primary, default)
   - GoogleSpeechEngine (secondary)
   - HTML/WebVTT styling removal
   
4. **Subtitle Processing** (`src/subshift/subtitles.py`)
   - SRT parsing and normalization
   - Minute-based indexing
   - Text cleaning (HTML, brackets, symbols)
   
5. **Alignment Algorithm** (`src/subshift/align.py`)
   - Levenshtein distance calculation
   - Search window management (±20 minutes, configurable)
   - Similarity scoring and matching
   
6. **Offset Calculation** (`src/subshift/offset.py`)
   - Per-sample offset calculation
   - Linear interpolation for timeline segments
   - Subtitle time correction
   
7. **Backup System** (`src/subshift/backup.py`)
   - Automated file retention (50 files <150KB, 25 files >150KB)
   - ISO-8601 timestamped copies
   
8. **Logging System** (`src/subshift/logging.py`)
   - 5MB rotation on startup
   - Rich integration for color output
   - INFO default, DEBUG with --debug flag

### Key Algorithms

#### Audio Sampling Strategy
```python
# Extract 4 random 1-minute samples
duration = get_video_duration( video_file );
if duration is None:
    # Fallback: TV=20min, Movies=90min based on filename heuristics
    duration = 20*60 if is_tv_show( video_file ) else 90*60;

# Sample every 5 minutes, up to 15 samples max
sample_interval = 5 * 60  # 5 minutes
max_samples = min( 15, duration // sample_interval );
sample_times = random.sample( range( 0, duration, sample_interval ), 4 );
```

#### Levenshtein Matching
```python
# Similarity threshold: 70% (30% error tolerance)
similarity = 1 - (levenshtein_distance / max( len( subtitle_text ), len( ai_text ) ));
is_match = similarity >= 0.7 and len( subtitle_text ) >= 40;
```

#### Offset Interpolation
```python
# Linear interpolation between sample points
for timestamp in subtitle_timestamps:
    # Find surrounding sample offsets
    before_sample = find_previous_sample( timestamp );
    after_sample = find_next_sample( timestamp );
    
    # Interpolate offset
    offset = interpolate_linear( timestamp, before_sample, after_sample );
    corrected_timestamp = timestamp + offset;
```

### Configuration

All configuration via command line arguments with environment variable overrides:

```bash
subshift --video movie.mp4 --subs movie.srt \
         --search-window 20 \
         --similarity-threshold 0.7 \
         --min-chars 40 \
         --api openai \
         --debug
```

Environment variables:
- `OPENAI_API_KEY` - OpenAI Whisper API key
- `GOOGLE_PLACES_API_KEY` - Google Speech-to-Text API key (note: user specifically requested this name)

### Output Format

SubShift produces:
1. **Corrected SRT file** - Original filename with `.corrected.srt` suffix
2. **Backup of original** - In `backup/` directory with ISO-8601 timestamp
3. **Analysis report** - Detailed matching results and applied offsets
4. **Debug output** - With `--debug`, shows AI vs subtitle comparisons

### Suggested Improvements

1. **Machine Learning Enhancement** - Train a model on common editing patterns
2. **Binary Subtitle Support** - Add .ass, .sub, .idx support (future work)
3. **SDH Detection** - Use AI to identify and strip sound descriptions
4. **Batch Processing** - Process multiple subtitle files simultaneously  
5. **Quality Metrics** - Confidence scoring for applied corrections
6. **Web Interface** - Browser-based UI for easier use
7. **Integration** - Plugin for Plex, Jellyfin, other media servers

### Testing Strategy

- Unit tests for each module
- Integration tests with sample media files
- Mock API responses for CI/CD
- Golden master test for end-to-end correction accuracy
- Performance benchmarks for large files

## Implementation Roadmap

### Phase 1: Core Framework (MVP)
- [x] Project structure and dependencies  
- [x] CLI argument parsing and logging
- [ ] Audio extraction with FFmpeg
- [ ] OpenAI Whisper integration
- [ ] SRT parsing and processing
- [ ] Levenshtein distance matching
- [ ] Basic offset calculation and application

### Phase 2: Enhanced Features  
- [ ] Google Speech-to-Text integration
- [ ] Interactive debug UI with curses
- [ ] Backup system with retention policies
- [ ] Error handling and retry logic
- [ ] Configuration validation

### Phase 3: Polish & Distribution
- [ ] Comprehensive test suite
- [ ] Documentation and examples
- [ ] Performance optimization
- [ ] Package for PyPI distribution
- [ ] CI/CD pipeline

### Phase 4: Advanced Features (Future)
- [ ] Binary subtitle support (.ass, .sub, etc)
- [ ] SDH removal with AI
- [ ] Web dashboard interface
- [ ] Media server integration
