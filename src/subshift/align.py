"""
Alignment algorithm for matching AI transcripts with subtitle text using Levenshtein distance.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
import Levenshtein
import re
from collections import Counter

from .audio import AudioSample
from .subtitles import SubtitleProcessor
from .logging import get_logger


@dataclass
class AlignmentMatch:
    """Represents a match between an audio sample and subtitle text."""
    
    audio_sample_index: int;        # Index of the audio sample
    audio_sample_timestamp: float;  # Start timestamp of audio sample (seconds)  
    audio_text: str;                # AI transcribed text
    subtitle_minute: int;           # Minute number where match was found
    subtitle_timestamp: float;      # Timestamp of first subtitle in the minute
    subtitle_text: str;             # Subtitle text for the minute
    levenshtein_distance: int;      # Raw Levenshtein distance
    similarity_score: float;        # Normalized similarity (0.0-1.0)
    is_match: bool;                 # Whether this passes the threshold
    
    def __repr__( self ):
        status = "✓" if self.is_match else "✗";
        return f"AlignmentMatch({status} sample={self.audio_sample_index}, " \
               f"minute={self.subtitle_minute}, similarity={self.similarity_score:.2f})";


class AlignmentEngine:
    """
    Alignment engine for matching audio transcripts with subtitle text.
    
    Uses Levenshtein distance with configurable similarity threshold.
    Searches within a time window around each audio sample.
    """
    
    def __init__( self, similarity_threshold: float = 0.7, search_window: int = 20, min_chars: int = 40 ):
        self.logger = get_logger();
        self.similarity_threshold = similarity_threshold;
        self.search_window = search_window;
        self.min_chars = min_chars;
    
    def calculate_levenshtein_similarity( self, text1: str, text2: str ) -> Tuple[int, float]:
        """
        Calculate basic Levenshtein distance and similarity score.
        
        Args:
            text1: First text string
            text2: Second text string
            
        Returns:
            Tuple of (levenshtein_distance, similarity_score)
            similarity_score = 1 - (distance / max_length)
        """
        if not text1 or not text2:
            return float( 'inf' ), 0.0;
        
        distance = Levenshtein.distance( text1, text2 );
        max_length = max( len( text1 ), len( text2 ) );
        
        if max_length == 0:
            return 0, 1.0;
        
        similarity = 1.0 - ( distance / max_length );
        return distance, similarity;
    
    def calculate_weighted_similarity( self, audio_text: str, subtitle_text: str, audio_timestamp: float, subtitle_minute: int ) -> Tuple[int, float]:
        """
        Calculate weighted similarity score using multiple factors for better accuracy.
        
        Factors:
        1. Levenshtein distance (base score)
        2. Word overlap bonus
        3. Sentence structure similarity
        4. Dialogue vs music detection
        5. Timing proximity bonus
        
        Args:
            audio_text: AI transcribed text
            subtitle_text: Subtitle text
            audio_timestamp: Audio sample timestamp (seconds)
            subtitle_minute: Subtitle minute
            
        Returns:
            Tuple of (levenshtein_distance, weighted_similarity_score)
        """
        if not audio_text or not subtitle_text:
            return float( 'inf' ), 0.0;
        
        # Base Levenshtein similarity
        distance, base_similarity = self.calculate_levenshtein_similarity( audio_text, subtitle_text );
        
        # Factor 1: Word overlap bonus (important words matching)
        audio_words = set( audio_text.lower().split() );
        subtitle_words = set( subtitle_text.lower().split() );
        
        # Filter out common words that don't add meaning
        stopwords = { 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'this', 'that', 'these', 'those' };
        meaningful_audio = audio_words - stopwords;
        meaningful_subtitle = subtitle_words - stopwords;
        
        if meaningful_audio and meaningful_subtitle:
            word_overlap = len( meaningful_audio & meaningful_subtitle ) / len( meaningful_audio | meaningful_subtitle );
            word_bonus = word_overlap * 0.15;  # Up to 15% bonus for good word overlap
        else:
            word_bonus = 0.0;
        
        # Factor 2: Sentence structure similarity (punctuation patterns, length)
        audio_sentences = len( re.split( r'[.!?]+', audio_text ) );
        subtitle_sentences = len( re.split( r'[.!?]+', subtitle_text ) );
        
        if max( audio_sentences, subtitle_sentences ) > 0:
            structure_similarity = 1.0 - abs( audio_sentences - subtitle_sentences ) / max( audio_sentences, subtitle_sentences );
            structure_bonus = structure_similarity * 0.05;  # Up to 5% bonus for similar structure
        else:
            structure_bonus = 0.0;
        
        # Factor 3: Content type detection (dialogue vs music/effects)
        music_indicators = { 'music', 'song', 'singing', 'melody', 'tune', 'beat', 'rhythm', 'instrumental' };
        dialogue_indicators = { 'said', 'told', 'asked', 'replied', 'answered', 'explained', 'whispered', 'shouted', 'called' };
        
        audio_music_score = len( meaningful_audio & music_indicators ) / max( len( meaningful_audio ), 1 );
        subtitle_music_score = len( meaningful_subtitle & music_indicators ) / max( len( meaningful_subtitle ), 1 );
        audio_dialogue_score = len( meaningful_audio & dialogue_indicators ) / max( len( meaningful_audio ), 1 );
        subtitle_dialogue_score = len( meaningful_subtitle & dialogue_indicators ) / max( len( meaningful_subtitle ), 1 );
        
        # Bonus if both are same type (both music or both dialogue)
        if ( audio_music_score > 0.1 and subtitle_music_score > 0.1 ) or ( audio_dialogue_score > 0.1 and subtitle_dialogue_score > 0.1 ):
            content_bonus = 0.08;  # 8% bonus for matching content type
        else:
            content_bonus = 0.0;
        
        # Factor 4: Timing proximity bonus
        expected_subtitle_time = subtitle_minute * 60;
        time_diff = abs( audio_timestamp - expected_subtitle_time );
        max_time_diff = self.search_window * 60;  # Convert search window to seconds
        
        if max_time_diff > 0:
            timing_proximity = 1.0 - ( time_diff / max_time_diff );
            timing_bonus = max( 0, timing_proximity * 0.1 );  # Up to 10% bonus for close timing
        else:
            timing_bonus = 0.0;
        
        # Calculate weighted similarity
        weighted_similarity = min( 1.0, base_similarity + word_bonus + structure_bonus + content_bonus + timing_bonus );
        
        # Debug logging for significant adjustments
        total_bonus = word_bonus + structure_bonus + content_bonus + timing_bonus;
        if total_bonus > 0.1:  # Significant bonus
            self.logger.debug( f"Similarity boost: {base_similarity:.3f} -> {weighted_similarity:.3f} " \
                             f"(word:{word_bonus:.3f}, struct:{structure_bonus:.3f}, content:{content_bonus:.3f}, timing:{timing_bonus:.3f})" );
        
        return distance, weighted_similarity;
    
    def find_best_match( self, audio_sample: AudioSample, subtitle_processor: SubtitleProcessor ) -> Optional[AlignmentMatch]:
        """
        Find the best subtitle match for an audio sample.
        
        Searches within a time window around the audio sample timestamp,
        comparing AI transcript with subtitle text using Levenshtein distance.
        
        Args:
            audio_sample: AudioSample with transcription
            subtitle_processor: SubtitleProcessor with loaded subtitles
            
        Returns:
            Best AlignmentMatch or None if no good match found
        """
        if not audio_sample.transcription:
            self.logger.warning( f"Audio sample {audio_sample.index} has no transcription" );
            return None;
        
        # Calculate center minute for search (audio sample timestamp)
        center_minute = int( audio_sample.start_timestamp // 60 );
        
        # Search within time window
        candidates = subtitle_processor.search_text_in_window(
            audio_sample.transcription,
            center_minute,
            self.search_window
        );
        
        if not candidates:
            self.logger.debug( f"No subtitle candidates found for sample {audio_sample.index}" );
            return None;
        
        best_match = None;
        best_similarity = 0.0;
        
        self.logger.debug( f"Evaluating {len( candidates )} candidates for sample {audio_sample.index}" );
        
        for minute, subtitle_text in candidates:
            # Skip if subtitle text is too short
            if len( subtitle_text ) < self.min_chars:
                continue;
            
            # Calculate weighted similarity for better accuracy
            distance, similarity = self.calculate_weighted_similarity(
                audio_sample.transcription.lower(),
                subtitle_text.lower(),
                audio_sample.start_timestamp,
                minute
            );
            
            # Check if this is a passing match
            is_match = similarity >= self.similarity_threshold and len( subtitle_text ) >= self.min_chars;
            
            # Get subtitle timestamp (first subtitle in this minute)
            subtitle_timestamp = None;
            if minute in subtitle_processor.minute_index:
                first_subtitle = min( subtitle_processor.minute_index[minute], key=lambda x: x.start_time );
                subtitle_timestamp = first_subtitle.start_time;
            else:
                subtitle_timestamp = minute * 60.0;  # Fallback to minute boundary
            
            # Create match object
            match = AlignmentMatch(
                audio_sample_index=audio_sample.index,
                audio_sample_timestamp=audio_sample.start_timestamp,
                audio_text=audio_sample.transcription,
                subtitle_minute=minute,
                subtitle_timestamp=subtitle_timestamp,
                subtitle_text=subtitle_text,
                levenshtein_distance=distance,
                similarity_score=similarity,
                is_match=is_match
            );
            
            # Update best match if this is better
            if similarity > best_similarity:
                best_match = match;
                best_similarity = similarity;
        
        if best_match:
            status = "PASS" if best_match.is_match else "FAIL";
            self.logger.debug( f"Best match for sample {audio_sample.index}: {status} " \
                             f"(similarity={best_match.similarity_score:.3f}, minute={best_match.subtitle_minute})" );
        else:
            self.logger.debug( f"No matches found for sample {audio_sample.index}" );
        
        return best_match;
    
    def align_samples( self, audio_samples: List[AudioSample], subtitle_processor: SubtitleProcessor ) -> List[AlignmentMatch]:
        """
        Align multiple audio samples with subtitle text.
        
        Args:
            audio_samples: List of AudioSample objects with transcriptions
            subtitle_processor: SubtitleProcessor with loaded subtitles
            
        Returns:
            List of AlignmentMatch objects (may include failed matches)
        """
        self.logger.info( f"Aligning {len( audio_samples )} audio samples with subtitles" );
        
        matches = [];
        successful_matches = 0;
        
        for sample in audio_samples:
            match = self.find_best_match( sample, subtitle_processor );
            if match:
                matches.append( match );
                if match.is_match:
                    successful_matches += 1;
        
        self.logger.info( f"Found {successful_matches}/{len( matches )} successful matches " \
                         f"(threshold: {self.similarity_threshold:.1%})" );
        
        return matches;
    
    def display_matches( self, matches: List[AlignmentMatch], debug: bool = False ):
        """
        Display alignment results to console.
        
        Args:
            matches: List of AlignmentMatch objects
            debug: If True, show detailed comparison text
        """
        if not matches:
            self.logger.warning( "No matches to display" );
            return;
        
        self.logger.info( "\n=== ALIGNMENT RESULTS ===" );
        
        for match in matches:
            status = "✓ PASS" if match.is_match else "✗ FAIL";
            
            self.logger.info( f"\nSample {match.audio_sample_index}: {status} " \
                             f"(Similarity: {match.similarity_score:.1%})" );
            
            self.logger.info( f"  Audio Time: {match.audio_sample_timestamp/60:.1f}m" );
            self.logger.info( f"  Subtitle Time: {match.subtitle_minute}m" );
            
            if debug:
                self.logger.info( f"  Audio Text: \"{match.audio_text[:100]}...\"" );
                self.logger.info( f"  Subtitle Text: \"{match.subtitle_text[:100]}...\"" );
                self.logger.info( f"  Levenshtein Distance: {match.levenshtein_distance}" );
    
    def get_successful_matches( self, matches: List[AlignmentMatch] ) -> List[AlignmentMatch]:
        """Get only the successful matches that pass the similarity threshold."""
        return [ match for match in matches if match.is_match ];
    
    def calculate_alignment_stats( self, matches: List[AlignmentMatch] ) -> dict:
        """Calculate statistics about the alignment results."""
        if not matches:
            return {};
        
        successful = self.get_successful_matches( matches );
        
        similarities = [ match.similarity_score for match in matches ];
        avg_similarity = sum( similarities ) / len( similarities );
        
        distances = [ match.levenshtein_distance for match in matches if match.levenshtein_distance != float( 'inf' ) ];
        avg_distance = sum( distances ) / len( distances ) if distances else 0;
        
        stats = {
            'total_matches': len( matches ),
            'successful_matches': len( successful ),
            'success_rate': len( successful ) / len( matches ),
            'avg_similarity': avg_similarity,
            'avg_levenshtein_distance': avg_distance,
            'similarity_threshold': self.similarity_threshold,
            'search_window_minutes': self.search_window
        };
        
        return stats;
