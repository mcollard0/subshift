"""
Subtitle processing module for parsing, normalizing, and indexing SRT files.
"""
import re
from pathlib import Path
from typing import Dict, List, Tuple
import pysrt

from .logging import get_logger


class SubtitleEntry:
    """Represents a single subtitle entry with timing and text."""
    
    def __init__( self, index: int, start_time: float, end_time: float, text: str ):
        self.index = index;          # Subtitle index number
        self.start_time = start_time;  # Start time in seconds
        self.end_time = end_time;      # End time in seconds
        self.text = text;              # Original subtitle text
        self.cleaned_text = "";        # Cleaned text for comparison
    
    def __repr__( self ):
        return f"SubtitleEntry(index={self.index}, start={self.start_time:.1f}s, text='{self.text[:30]}...')";


class SubtitleProcessor:
    """
    SRT subtitle processor with normalization and minute-based indexing.
    
    Features:
    - SRT-only support (rejects other formats)
    - HTML/WebVTT tag removal
    - Bracketed description stripping
    - Emoji/symbol cleanup
    - Minute-based text aggregation
    - ≥40 character threshold filtering
    """
    
    def __init__( self, min_chars: int = 40 ):
        self.logger = get_logger();
        self.min_chars = min_chars;
        self.subtitle_entries = [];
        self.minute_index = {};  # minute -> list of SubtitleEntry objects
    
    def validate_subtitle_file( self, subtitle_file: Path ) -> bool:
        """
        Validate subtitle file format and existence.
        
        Args:
            subtitle_file: Path to subtitle file
            
        Returns:
            True if valid SRT file, False otherwise
        """
        if not subtitle_file.exists():
            self.logger.error( f"Subtitle file not found: {subtitle_file}" );
            return False;
        
        # Check file extension
        if subtitle_file.suffix.lower() != '.srt':
            self.logger.error( f"Only .srt files are supported, got: {subtitle_file.suffix}" );
            self.logger.error( "Unsupported formats: .ass, .sub, .idx, .sup, .stl, .scc" );
            return False;
        
        return True;
    
    def clean_subtitle_text( self, text: str ) -> str:
        """
        Clean subtitle text by removing HTML, WebVTT tags, and artifacts.
        
        Args:
            text: Raw subtitle text
            
        Returns:
            Cleaned text suitable for comparison
        """
        if not text:
            return "";
        
        # Remove HTML tags
        text = re.sub( r'<[^>]+>', '', text );
        
        # Remove WebVTT styling
        text = re.sub( r'<c\.[^>]*>', '', text );
        text = re.sub( r'</c>', '', text );
        
        # Remove bracketed descriptions
        text = re.sub( r'\[([^\]]+)\]', '', text );  # [music], [door slams]
        text = re.sub( r'\(([^)]+)\)', '', text );   # (laughter), (whispers)
        
        # Remove speaker labels (NAME:)
        text = re.sub( r'^[A-Z][A-Z\s]*:', '', text );
        
        # Remove common subtitle symbols
        text = re.sub( r'[♪♫★►▼→←↑↓]', '', text );
        
        # Remove multiple punctuation
        text = re.sub( r'[.]{2,}', '.', text );
        text = re.sub( r'[-]{2,}', '-', text );
        
        # Clean up whitespace
        text = re.sub( r'\s+', ' ', text );
        text = text.strip();
        
        # Convert to lowercase for case-insensitive comparison
        text = text.lower();
        
        return text;
    
    def parse_subtitle_file( self, subtitle_file: Path ) -> List[SubtitleEntry]:
        """
        Parse SRT subtitle file into SubtitleEntry objects.
        
        Args:
            subtitle_file: Path to SRT file
            
        Returns:
            List of SubtitleEntry objects
        """
        if not self.validate_subtitle_file( subtitle_file ):
            return [];
        
        self.logger.info( f"Parsing subtitle file: {subtitle_file}" );
        
        try:
            subs = pysrt.open( str( subtitle_file ) );
            
            self.subtitle_entries = [];
            for sub in subs:
                # Convert pysrt time to seconds
                start_seconds = ( 
                    sub.start.hours * 3600 + 
                    sub.start.minutes * 60 + 
                    sub.start.seconds + 
                    sub.start.milliseconds / 1000.0 
                );
                
                end_seconds = ( 
                    sub.end.hours * 3600 + 
                    sub.end.minutes * 60 + 
                    sub.end.seconds + 
                    sub.end.milliseconds / 1000.0 
                );
                
                # Create subtitle entry
                entry = SubtitleEntry( 
                    index=sub.index, 
                    start_time=start_seconds,
                    end_time=end_seconds,
                    text=sub.text 
                );
                
                # Clean text for comparison
                entry.cleaned_text = self.clean_subtitle_text( sub.text );
                
                self.subtitle_entries.append( entry );
            
            self.logger.info( f"Parsed {len( self.subtitle_entries )} subtitle entries" );
            return self.subtitle_entries;
            
        except Exception as e:
            self.logger.error( f"Failed to parse subtitle file: {e}" );
            return [];
    
    def create_minute_index( self ) -> Dict[int, List[SubtitleEntry]]:
        """
        Create minute-based index of subtitle entries.
        
        Groups subtitle entries by the minute they appear in,
        creating a lookup dictionary.
        
        Returns:
            Dictionary mapping minute number to list of SubtitleEntry objects
        """
        self.minute_index = {};
        
        for entry in self.subtitle_entries:
            # Calculate minute (0-based, as movies start at 0:00)
            minute = int( entry.start_time // 60 );
            
            if minute not in self.minute_index:
                self.minute_index[minute] = [];
            
            self.minute_index[minute].append( entry );
        
        self.logger.debug( f"Created minute index with {len( self.minute_index )} minutes" );
        return self.minute_index;
    
    def get_minute_text( self, minute: int ) -> str:
        """
        Get concatenated text for all subtitles in a specific minute.
        
        Args:
            minute: Minute number (0-based)
            
        Returns:
            Concatenated cleaned text for the minute
        """
        if minute not in self.minute_index:
            return "";
        
        texts = [];
        for entry in self.minute_index[minute]:
            if entry.cleaned_text:
                texts.append( entry.cleaned_text );
        
        combined_text = " ".join( texts );
        return combined_text;
    
    def get_minutes_with_min_chars( self ) -> List[int]:
        """
        Get list of minutes that have at least min_chars characters.
        
        Used to filter out sparse minutes that won't provide good matches.
        
        Returns:
            List of minute numbers that meet the character threshold
        """
        valid_minutes = [];
        
        for minute in sorted( self.minute_index.keys() ):
            minute_text = self.get_minute_text( minute );
            if len( minute_text ) >= self.min_chars:
                valid_minutes.append( minute );
        
        self.logger.info( f"Found {len( valid_minutes )} minutes with ≥{self.min_chars} characters" );
        return valid_minutes;
    
    def get_search_window( self, center_minute: int, search_window: int ) -> Tuple[int, int]:
        """
        Calculate search window bounds around a center minute.
        
        Args:
            center_minute: Center minute for search
            search_window: Search radius in minutes
            
        Returns:
            Tuple of (start_minute, end_minute) with bounds checking
        """
        start_minute = max( 0, center_minute - search_window );
        
        max_minute = max( self.minute_index.keys() ) if self.minute_index else 0;
        end_minute = min( max_minute, center_minute + search_window );
        
        return start_minute, end_minute;
    
    def search_text_in_window( self, target_text: str, center_minute: int, search_window: int = 20 ) -> List[Tuple[int, str]]:
        """
        Search for text within a time window around a center minute.
        
        Args:
            target_text: Text to search for
            center_minute: Center minute for search
            search_window: Search radius in minutes
            
        Returns:
            List of (minute, text) tuples within the search window
        """
        if not target_text or len( target_text ) < self.min_chars:
            return [];
        
        start_minute, end_minute = self.get_search_window( center_minute, search_window );
        
        results = [];
        for minute in range( start_minute, end_minute + 1 ):
            minute_text = self.get_minute_text( minute );
            if minute_text:
                results.append( ( minute, minute_text ) );
        
        return results;
    
    def get_subtitle_stats( self ) -> Dict:
        """Get statistics about the loaded subtitle file."""
        if not self.subtitle_entries:
            return {};
        
        total_entries = len( self.subtitle_entries );
        total_minutes = len( self.minute_index );
        
        # Calculate total duration
        if self.subtitle_entries:
            last_entry = max( self.subtitle_entries, key=lambda x: x.end_time );
            duration_seconds = last_entry.end_time;
            duration_minutes = duration_seconds / 60;
        else:
            duration_seconds = 0;
            duration_minutes = 0;
        
        # Calculate character statistics
        char_counts = [ len( entry.cleaned_text ) for entry in self.subtitle_entries ];
        avg_chars = sum( char_counts ) / len( char_counts ) if char_counts else 0;
        
        valid_minutes = len( self.get_minutes_with_min_chars() );
        
        stats = {
            'total_entries': total_entries,
            'total_minutes': total_minutes,
            'duration_seconds': duration_seconds,
            'duration_minutes': duration_minutes,
            'avg_chars_per_entry': avg_chars,
            'valid_minutes': valid_minutes,
            'min_char_threshold': self.min_chars
        };
        
        return stats;
