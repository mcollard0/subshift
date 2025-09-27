"""
SubShift - Subtitle synchronization utility.

Aligns out-of-sync subtitles to edited videos using AI transcripts 
and Levenshtein-based matching.
"""

__version__ = "0.1.0";
__author__ = "SubShift Project";
__license__ = "MIT";

# Import key components for external use
from .align import AlignmentEngine, AlignmentMatch
from .subtitles import SubtitleProcessor, SubtitleEntry
from .transcribe import TranscriptionEngine, WhisperEngine, GoogleSpeechEngine, create_transcription_engine
from .audio import AudioProcessor, AudioSample

# Export main classes
__all__ = [
    'AlignmentEngine',
    'AlignmentMatch', 
    'SubtitleProcessor',
    'SubtitleEntry',
    'TranscriptionEngine',
    'WhisperEngine',
    'GoogleSpeechEngine',
    'create_transcription_engine',
    'AudioProcessor',
    'AudioSample'
];
