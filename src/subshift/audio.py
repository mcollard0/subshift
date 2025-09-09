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
        self.sample_duration = 60; # 1 minute per sample
    
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
    
    def generate_sample_times( self, duration: float, num_samples: int = None ) -> List[float]:
        """
        Generate sample start times based on video duration.
        
        Strategy:
        - Take one sample every 5 minutes starting from 5:00
        - If more than 15 samples available, randomly select 15
        - Each sample is 1 minute long
        - num_samples parameter is ignored (kept for compatibility)
        
        Args:
            duration: Video duration in seconds
            num_samples: Ignored (kept for backward compatibility)
            
        Returns:
            List of start times in seconds
        """
        sample_interval = 5 * 60;  # 5 minutes
        start_offset = 5 * 60;     # Start at 5:00 minutes
        
        # Generate all possible sample positions every 5 minutes
        all_positions = [];
        current_pos = start_offset;
        
        while current_pos + self.sample_duration < duration:
            all_positions.append( current_pos );
            current_pos += sample_interval;
        
        if not all_positions:
            self.logger.warning( "No valid sample positions found" );
            return [];
        
        # If more than 15 samples, randomly select 15
        if len( all_positions ) > 15:
            sample_times = random.sample( all_positions, 15 );
            self.logger.info( f"Video has {len( all_positions )} possible samples, randomly selected 15" );
        else:
            sample_times = all_positions;
            self.logger.info( f"Using all {len( sample_times )} available samples" );
        
        sample_times.sort();  # Sort for consistent processing
        
        self.logger.info( f"Sample times (minutes): {[ t/60 for t in sample_times ]}" );
        return sample_times;
    
    def extract_audio_sample( self, video_file: Path, start_time: float, index: int ) -> Optional[AudioSample]:
        """
        Extract a single audio sample from video file.
        
        Args:
            video_file: Path to input video
            start_time: Start time in seconds
            index: Sample index for naming
            
        Returns:
            AudioSample object or None if extraction fails
        """
        output_file = self.temp_dir / f"sample_{index:03d}_{int( start_time )}.wav";
        
        try:
            self.logger.debug( f"Extracting sample {index} from {start_time}s to {output_file}" );
            
            # FFmpeg command: extract audio segment with specific format
            stream = ffmpeg.input( str( video_file ), ss=start_time, t=self.sample_duration );
            stream = ffmpeg.output(
                stream,
                str( output_file ),
                acodec='pcm_s16le',
                ar=self.sample_rate,
                ac=self.channels,
                f='wav'
            );
            
            ffmpeg.run( stream, overwrite_output=True, quiet=True );
            
            # Verify extraction succeeded
            if output_file.exists() and output_file.stat().st_size > 0:
                sample = AudioSample( index, start_time, output_file );
                self.logger.debug( f"Successfully extracted {sample}" );
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
        
        # Generate sample times (every 5 minutes, max 15)
        sample_times = self.generate_sample_times( duration );
        if not sample_times:
            self.logger.error( "No sample times generated" );
            return [];
        
        # Extract samples with retry logic
        samples = [];
        failed_indices = [];
        
        for i, start_time in enumerate( sample_times ):
            sample = self.extract_audio_sample( video_file, start_time, i );
            if sample:
                samples.append( sample );
            else:
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
