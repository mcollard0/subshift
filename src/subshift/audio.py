"""
Audio processing module for extracting and sampling audio from video files.
"""
import random
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
import ffmpeg
import subprocess

from .logging import get_logger
import statistics


class AudioSample:
    """Represents a single audio sample extracted from a video."""
    
    def __init__( self, index: int, start_timestamp: float, file_path: Path ):
        self.index = index;           # Sample index (0-based)
        self.start_timestamp = start_timestamp;  # Start time in seconds  
        self.file_path = file_path;   # Path to extracted audio file
        self.transcription = None;    # Will be filled by transcription engine
    
    def __repr__( self ):
        return f"AudioSample(index={self.index}, start={self.start_timestamp}s, path={self.file_path})";


class AudioProcessor:
    """
    Audio processing utilities for video file analysis and sampling.
    
    Features:
    - Video duration detection  
    - Random audio sampling strategy (4 samples by default)
    - FFmpeg integration for audio extraction
    - Format conversion for AI compatibility (16kHz mono PCM)
    """
    
    def __init__( self, temp_dir: Optional[Path] = None, debug: bool = False ):
        self.logger = get_logger( debug=debug );
        self.temp_dir = Path( temp_dir ) if temp_dir else Path( "tmp" );
        self.temp_dir.mkdir( exist_ok=True );
        
        # Audio extraction settings
        self.sample_rate = 16000;  # 16kHz for AI compatibility
        self.channels = 1;         # Mono
        self.sample_durations = [ 30, 60, 90 ];  # Multi-duration sampling for better coverage
        self.primary_duration = 60; # Primary duration for most samples
    
    def get_video_duration( self, video_file: Path ) -> Optional[float]:
        """
        Get video duration in seconds using FFprobe.
        
        Returns:
            Duration in seconds, or None if detection fails
        """
        try:
            probe = ffmpeg.probe( str( video_file ) );
            duration = float( probe['format']['duration'] );
            self.logger.debug( f"Video duration: {duration:.2f} seconds ({duration/60:.1f} minutes)" );
            return duration;
        except Exception as e:
            self.logger.warning( f"Could not determine video duration: {e}" );
            return None;
    
    def estimate_duration_from_filename( self, video_file: Path ) -> float:
        """
        Estimate duration based on filename patterns.
        
        Uses heuristics:
        - TV shows (contains S##E##, season/episode): 20 minutes
        - Movies (default): 90 minutes
        
        Returns:
            Estimated duration in seconds
        """
        filename = video_file.name.lower();
        
        # TV show patterns
        tv_patterns = [ 's', 'season', 'episode', 'e' ];
        is_tv = any( pattern in filename for pattern in tv_patterns );
        
        if is_tv:
            duration = 20 * 60;  # 20 minutes
            self.logger.info( f"Estimated TV show duration: {duration/60} minutes" );
        else:
            duration = 90 * 60;  # 90 minutes  
            self.logger.info( f"Estimated movie duration: {duration/60} minutes" );
        
        return duration;
    
    def generate_sample_times( self, duration: float, num_samples: int = None, use_sliding_window: bool = True, phase: str = "initial" ) -> List[float]:
        """
        Generate sample start times based on video duration using improved sampling strategy.
        
        Enhanced Strategy:
        - Use sliding window sampling for better dialogue coverage
        - Primary samples every 2.5 minutes for dense coverage  
        - Skip first 3 minutes (credits/intro) and last 5 minutes (credits/outro)
        - Each sample is 1 minute long
        - Intelligently limit to ~20 samples for API efficiency
        
        Args:
            duration: Video duration in seconds
            num_samples: Maximum samples to extract (default: auto-calculated)
            use_sliding_window: Use overlapping samples for better coverage
            
        Returns:
            List of start times in seconds
        """
        if use_sliding_window:
            # Enhanced sliding window strategy
            sample_interval = 2.5 * 60;  # 2.5 minutes for dense coverage
            start_offset = 3 * 60;       # Start at 3:00 (skip intro)
            end_buffer = 5 * 60;         # Skip last 5 minutes (credits)
        else:
            # Legacy strategy for compatibility
            sample_interval = 5 * 60;
            start_offset = 5 * 60;
            end_buffer = 0;
        
        effective_duration = duration - end_buffer;
        
        # Generate all possible sample positions
        all_positions = [];
        current_pos = start_offset;
        
        while current_pos + self.primary_duration < effective_duration:
            all_positions.append( current_pos );
            current_pos += sample_interval;
        
        if not all_positions:
            self.logger.warning( "No valid sample positions found" );
            return [];
        
        # Adaptive sample selection based on phase
        if phase == "initial":
            max_samples = num_samples if num_samples else 12;  # Start conservative
        elif phase == "consistent":
            max_samples = num_samples if num_samples else 8;   # Reduce for good sync
        elif phase == "inconsistent":
            max_samples = num_samples if num_samples else 35;  # Increase for bad sync
        else:
            max_samples = num_samples if num_samples else 20;  # Default fallback
        
        if len( all_positions ) <= max_samples:
            sample_times = all_positions;
            self.logger.info( f"Using all {len( sample_times )} available samples" );
        else:
            # For longer videos, use strategic selection:
            # - Ensure good coverage across the entire duration
            # - Prefer samples from dialogue-heavy middle sections
            step = len( all_positions ) / max_samples;
            sample_times = [];
            
            for i in range( max_samples ):
                index = int( i * step );
                if index < len( all_positions ):
                    sample_times.append( all_positions[index] );
            
            self.logger.info( f"Video has {len( all_positions )} possible samples, selected {len( sample_times )} strategically" );
        
        sample_times.sort();  # Sort for consistent processing
        
        interval_desc = "sliding window (2.5m)" if use_sliding_window else "fixed interval (5m)";
        self.logger.info( f"Sample times ({interval_desc}): {[ round( t/60, 1 ) for t in sample_times ]}" );
        return sample_times;
    
    def _apply_audio_preprocessing( self, stream, output_file: Path ):
        """
        Apply enhanced audio preprocessing for better AI transcription quality.
        
        Preprocessing steps:
        1. Noise reduction for cleaner speech
        2. Audio normalization to consistent levels
        3. High-pass filter to remove low-frequency noise
        4. Compander to enhance dialogue clarity
        5. Format conversion to AI-optimal specs
        
        Args:
            stream: FFmpeg input stream
            output_file: Output file path
            
        Returns:
            Configured FFmpeg output stream
        """
        # Build audio filter chain for enhanced transcription
        filters = [];
        
        # 1. High-pass filter to remove low-frequency rumble/noise (below 80Hz)
        filters.append( 'highpass=f=80' );
        
        # 2. Audio normalization to -16dB (good level for speech recognition)
        filters.append( 'loudnorm=I=-16:LRA=11:TP=-2' );
        
        # 3. Noise reduction using FFmpeg's afftdn filter
        # This helps with robot sounds, mechanical noise, etc.
        filters.append( 'afftdn=nr=12:nf=-25' );
        
        # 4. Compander for dialogue enhancement
        # Compress loud sounds, expand quiet sounds for more even levels
        filters.append( 'compand=attacks=0.3:decays=0.8:points=-80/-80|-45/-15|-27/-9|0/-7|20/-7' );
        
        # 5. Final level adjustment and limiting
        filters.append( 'alimiter=level_in=1:level_out=0.8:limit=0.9' );
        
        # Combine all filters
        filter_string = ','.join( filters );
        
        self.logger.debug( f"Audio preprocessing chain: {filter_string}" );
        
        # Apply filters and output configuration
        stream = ffmpeg.output(
            stream,
            str( output_file ),
            acodec='pcm_s16le',          # 16-bit PCM for compatibility
            ar=self.sample_rate,         # 16kHz sample rate
            ac=self.channels,            # Mono channel
            af=filter_string,            # Apply preprocessing filters
            f='wav'                      # WAV format
        );
        
        return stream;
    
    def extract_audio_sample( self, video_file: Path, start_time: float, index: int, duration: int = None ) -> Optional[AudioSample]:
        """
        Extract a single audio sample from video file with adaptive duration.
        
        Args:
            video_file: Path to input video
            start_time: Start time in seconds
            index: Sample index for naming
            duration: Sample duration in seconds (default: primary_duration)
            
        Returns:
            AudioSample object or None if extraction fails
        """
        if duration is None:
            duration = self.primary_duration;
        
        output_file = self.temp_dir / f"sample_{index:03d}_{int( start_time )}_{duration}s.wav";
        
        try:
            self.logger.debug( f"Extracting sample {index} from {start_time}s ({duration}s duration) to {output_file}" );
            
            # FFmpeg command: extract audio segment with specific format
            stream = ffmpeg.input( str( video_file ), ss=start_time, t=duration );
            # Enhanced audio preprocessing for better transcription quality
            stream = self._apply_audio_preprocessing( stream, output_file );
            
            ffmpeg.run( stream, overwrite_output=True, quiet=True );
            
            # Verify extraction succeeded
            if output_file.exists() and output_file.stat().st_size > 0:
                sample = AudioSample( index, start_time, output_file );
                sample.duration = duration;  # Store duration for reference
                self.logger.debug( f"Successfully extracted {duration}s sample: {sample}" );
                return sample;
            else:
                self.logger.error( f"Audio extraction failed for sample {index}" );
                return None;
                
        except ffmpeg.Error as e:
            self.logger.error( f"FFmpeg error extracting sample {index}: {e}" );
            return None;
        except Exception as e:
            self.logger.error( f"Unexpected error extracting sample {index}: {e}" );
            return None;
    
    def extract_multi_duration_samples( self, video_file: Path, sample_times: List[float], max_samples: int = 20 ) -> List[AudioSample]:
        """
        Extract samples with multiple durations for comprehensive coverage.
        
        Strategy:
        - 70% of samples: 60s (standard duration)
        - 20% of samples: 30s (catch quick dialogue)
        - 10% of samples: 90s (full context for complex scenes)
        
        Args:
            video_file: Path to input video file
            sample_times: List of sample start times
            max_samples: Maximum number of samples to extract
            
        Returns:
            List of successfully extracted AudioSample objects
        """
        samples = [];
        total_samples = min( len( sample_times ), max_samples );
        
        # Calculate distribution
        standard_count = int( total_samples * 0.7 );  # 70% standard (60s)
        short_count = int( total_samples * 0.2 );     # 20% short (30s)
        long_count = total_samples - standard_count - short_count;  # Rest long (90s)
        
        self.logger.info( f"Multi-duration extraction plan: {standard_count}×60s, {short_count}×30s, {long_count}×90s" );
        
        for i, start_time in enumerate( sample_times[:total_samples] ):
            # Determine duration based on distribution
            if i < standard_count:
                duration = 60;  # Standard
            elif i < standard_count + short_count:
                duration = 30;  # Short
            else:
                duration = 90;  # Long
            
            sample = self.extract_audio_sample( video_file, start_time, i, duration );
            if sample:
                samples.append( sample );
        
        return samples;
    
    def extract_audio_samples( self, video_file: Path, num_samples: int = None ) -> List[AudioSample]:
        """
        Extract multiple audio samples from video file with retry logic.
        
        Uses new sampling strategy: one sample every 5 minutes, max 15 total.
        
        Args:
            video_file: Path to input video file
            num_samples: Ignored (kept for backward compatibility)
            
        Returns:
            List of successfully extracted AudioSample objects
        """
        self.logger.info( f"Starting audio extraction from {video_file}" );
        
        # Get video duration
        duration = self.get_video_duration( video_file );
        if duration is None:
            duration = self.estimate_duration_from_filename( video_file );
        
        # Generate sample times using sliding window strategy
        sample_times = self.generate_sample_times( duration, num_samples );
        if not sample_times:
            self.logger.error( "No sample times generated" );
            return [];
        
        # Extract samples using multi-duration strategy for better coverage
        max_samples = num_samples if num_samples else 20;
        samples = self.extract_multi_duration_samples( video_file, sample_times, max_samples );
        
        # Identify failed extractions for potential retry
        failed_indices = [];
        for i, start_time in enumerate( sample_times[:max_samples] ):
            if i >= len( samples ) or not samples[i] or samples[i].start_timestamp != start_time:
                failed_indices.append( i );
        
        # Retry failed extractions once with different random times
        max_samples = num_samples if num_samples is not None else len( sample_times );
        if failed_indices and len( samples ) < max_samples:
            self.logger.info( f"Retrying {len( failed_indices )} failed extractions" );
            
            # Generate new sample times for retries
            all_positions = list( range( int( 5*60 ), int( duration-60 ), int( 5*60 ) ) );
            used_times = set( int( sample.start_timestamp ) for sample in samples );
            available_times = [ t for t in all_positions if t not in used_times ];
            
            retry_times = random.sample( available_times, min( len( failed_indices ), len( available_times ) ) );
            
            for retry_idx, start_time in enumerate( retry_times ):
                sample = self.extract_audio_sample( video_file, start_time, len( samples ) + retry_idx );
                if sample:
                    samples.append( sample );
        
        self.logger.info( f"Successfully extracted {len( samples )} audio samples" );
        return samples;
    
    def cleanup_samples( self, samples: List[AudioSample] ):
        """Clean up temporary audio sample files."""
        for sample in samples:
            try:
                if sample.file_path.exists():
                    sample.file_path.unlink();
                    self.logger.debug( f"Cleaned up {sample.file_path}" );
            except Exception as e:
                self.logger.warning( f"Could not clean up {sample.file_path}: {e}" );


class AdaptiveSamplingCoordinator:
    """
    Coordinates adaptive sampling based on timing consistency analysis.
    
    Enhanced Strategy (higher baseline for better accuracy):
    1. Initial Phase: Start with 16 samples for robust baseline assessment
    2. Analyze timing consistency from initial results
    3. Consistent timing (<2s variance): Maintain 12 samples (reliability over cost)
    4. Inconsistent timing (>5s variance): Increase to 40+ samples (maximum accuracy)
    5. Moderate variance (2-5s): Use enhanced standard 24 samples
    
    This provides better coverage for challenging content like animated films.
    """
    
    def __init__( self, debug: bool = False ):
        self.logger = get_logger( debug=debug );
        self.timing_history = [];  # Store offset measurements for analysis
        self.consistency_threshold_low = 2.0;   # Seconds - good consistency
        self.consistency_threshold_high = 5.0;  # Seconds - poor consistency
    
    def analyze_timing_consistency( self, offset_points: List[float] ) -> str:
        """
        Analyze timing consistency from offset measurements.
        
        Args:
            offset_points: List of timing offset measurements in seconds
            
        Returns:
            String: "consistent", "inconsistent", or "moderate"
        """
        if len( offset_points ) < 3:
            return "insufficient_data";
        
        # Calculate variance in timing offsets
        mean_offset = statistics.mean( offset_points );
        variance = statistics.variance( offset_points ) if len( offset_points ) > 1 else 0;
        std_dev = statistics.stdev( offset_points ) if len( offset_points ) > 1 else 0;
        
        # Calculate range (max - min)
        offset_range = max( offset_points ) - min( offset_points );
        
        self.logger.debug( f"Timing analysis: mean={mean_offset:.2f}s, std_dev={std_dev:.2f}s, range={offset_range:.2f}s" );
        
        # Store for historical analysis
        self.timing_history.extend( offset_points );
        
        # Classify consistency
        if std_dev <= self.consistency_threshold_low and offset_range <= 3.0:
            return "consistent";      # Good sync, can reduce samples
        elif std_dev >= self.consistency_threshold_high or offset_range >= 8.0:
            return "inconsistent";    # Poor sync, need more samples
        else:
            return "moderate";        # Standard sampling
    
    def recommend_sample_count( self, consistency: str, current_success_rate: float = None ) -> int:
        """
        Recommend optimal sample count based on consistency analysis.
        
        Args:
            consistency: Result from analyze_timing_consistency()
            current_success_rate: Optional success rate from alignment (0.0-1.0)
            
        Returns:
            Recommended number of samples
        """
        base_recommendations = {
            "consistent": 12,    # Higher baseline for reliability
            "moderate": 24,      # Increased standard sampling
            "inconsistent": 40,  # Higher maximum for difficult content
            "insufficient_data": 16  # Better initial coverage
        };
        
        recommended = base_recommendations.get( consistency, 20 );
        
        # Adjust based on success rate if available
        if current_success_rate is not None:
            if current_success_rate < 0.5:  # Very poor success
                recommended = min( 40, int( recommended * 1.4 ) );  # Increase samples significantly
            elif current_success_rate > 0.8:  # Very good success
                recommended = max( 6, int( recommended * 0.8 ) );   # Reduce samples slightly
        
        self.logger.info( f"Adaptive sampling recommendation: {recommended} samples (consistency: {consistency})" );
        return recommended;
    
    def should_resample( self, offset_points: List[float], current_samples: int ) -> bool:
        """
        Determine if additional resampling is needed based on results.
        
        Args:
            offset_points: Current offset measurements
            current_samples: Number of samples used
            
        Returns:
            True if resampling recommended
        """
        if len( offset_points ) < 2:
            return True;  # Need more data
        
        consistency = self.analyze_timing_consistency( offset_points );
        recommended_samples = self.recommend_sample_count( consistency );
        
        # Resample if we need significantly more samples
        if recommended_samples > current_samples * 1.5:
            self.logger.info( f"Resampling recommended: {current_samples} -> {recommended_samples} samples" );
            return True;
        
        return False;
    
    def get_cost_estimate( self, sample_count: int ) -> float:
        """
        Estimate OpenAI Whisper costs for given sample count.
        
        Args:
            sample_count: Number of audio samples
            
        Returns:
            Estimated cost in USD
        """
        # Multi-duration average: 70% × 1min + 20% × 0.5min + 10% × 1.5min = 0.95min avg
        avg_duration_minutes = 0.95;
        whisper_cost_per_minute = 0.006;
        
        total_audio_minutes = sample_count * avg_duration_minutes;
        total_cost = total_audio_minutes * whisper_cost_per_minute;
        
        return total_cost;
