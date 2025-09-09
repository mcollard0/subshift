"""
Offset calculation and subtitle correction module.
"""
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
import pysrt

from .align import AlignmentMatch
from .subtitles import SubtitleProcessor
from .logging import get_logger


class OffsetCalculator:
    """
    Calculate time offsets from alignment matches and apply corrections to subtitles.
    
    Features:
    - Per-sample offset calculation (subtitle_ts - audio_ts)
    - Linear interpolation between sample points
    - Subtitle file backup and correction
    - SRT format preservation
    """
    
    def __init__( self ):
        self.logger = get_logger();
        self.offsets = [];  # List of (timestamp, offset) tuples
    
    def calculate_sample_offsets( self, matches: List[AlignmentMatch] ) -> List[Tuple[float, float]]:
        """
        Calculate time offsets from successful alignment matches.
        
        Offset = subtitle_timestamp - audio_sample_timestamp
        Positive offset means subtitles are ahead (need to be delayed)
        Negative offset means subtitles are behind (need to be advanced)
        
        Args:
            matches: List of AlignmentMatch objects
            
        Returns:
            List of (audio_timestamp, offset_seconds) tuples
        """
        successful_matches = [ match for match in matches if match.is_match ];
        
        if not successful_matches:
            self.logger.warning( "No successful matches for offset calculation" );
            return [];
        
        self.offsets = [];
        
        for match in successful_matches:
            # Calculate offset: subtitle time - audio time
            offset = match.subtitle_timestamp - match.audio_sample_timestamp;
            
            self.offsets.append( ( match.audio_sample_timestamp, offset ) );
            
            self.logger.debug( f"Sample {match.audio_sample_index}: " \
                             f"audio={match.audio_sample_timestamp/60:.1f}m, " \
                             f"subtitle={match.subtitle_timestamp/60:.1f}m, " \
                             f"offset={offset:.1f}s" );
        
        # Sort by timestamp for interpolation
        self.offsets.sort( key=lambda x: x[0] );
        
        self.logger.info( f"Calculated {len( self.offsets )} offset points" );
        return self.offsets;
    
    def interpolate_offset( self, timestamp: float ) -> float:
        """
        Interpolate offset for a given timestamp using linear interpolation.
        
        Args:
            timestamp: Timestamp in seconds
            
        Returns:
            Interpolated offset in seconds
        """
        if not self.offsets:
            return 0.0;
        
        # If only one offset point, use it for everything
        if len( self.offsets ) == 1:
            return self.offsets[0][1];
        
        # If timestamp is before first sample, use first offset
        if timestamp <= self.offsets[0][0]:
            return self.offsets[0][1];
        
        # If timestamp is after last sample, use last offset
        if timestamp >= self.offsets[-1][0]:
            return self.offsets[-1][1];
        
        # Find surrounding offset points for interpolation
        for i in range( len( self.offsets ) - 1 ):
            t1, offset1 = self.offsets[i];
            t2, offset2 = self.offsets[i + 1];
            
            if t1 <= timestamp <= t2:
                # Linear interpolation
                if t2 == t1:  # Avoid division by zero
                    return offset1;
                
                ratio = ( timestamp - t1 ) / ( t2 - t1 );
                interpolated_offset = offset1 + ratio * ( offset2 - offset1 );
                
                return interpolated_offset;
        
        # Fallback (shouldn't reach here)
        return 0.0;
    
    def create_backup( self, subtitle_file: Path ) -> Path:
        """
        Create backup of original subtitle file with timestamp.
        
        Args:
            subtitle_file: Path to original subtitle file
            
        Returns:
            Path to backup file
        """
        backup_dir = Path( "backup" );
        backup_dir.mkdir( exist_ok=True );
        
        timestamp = datetime.now().isoformat().replace( ":", "-" );
        backup_name = f"{subtitle_file.stem}.{timestamp}{subtitle_file.suffix}";
        backup_path = backup_dir / backup_name;
        
        shutil.copy2( subtitle_file, backup_path );
        self.logger.info( f"Created backup: {backup_path}" );
        
        return backup_path;
    
    def apply_corrections( self, subtitle_file: Path, dry_run: bool = False ) -> Path:
        """
        Apply calculated offsets to subtitle file and save corrected version.
        
        Args:
            subtitle_file: Path to original subtitle file
            dry_run: If True, don't actually save the corrected file
            
        Returns:
            Path to corrected subtitle file (or would-be path if dry_run)
        """
        if not self.offsets:
            raise ValueError( "No offsets calculated. Run calculate_sample_offsets first." );
        
        self.logger.info( f"Applying corrections to {subtitle_file}" );
        
        # Load subtitle file
        try:
            subs = pysrt.open( str( subtitle_file ) );
        except Exception as e:
            raise ValueError( f"Failed to load subtitle file: {e}" );
        
        corrections_applied = 0;
        
        for sub in subs:
            # Convert start time to seconds for offset calculation
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
            
            # Calculate interpolated offset for this subtitle
            offset = self.interpolate_offset( start_seconds );
            
            # Apply offset (subtract because positive offset means subtitles are ahead)
            new_start_seconds = start_seconds - offset;
            new_end_seconds = end_seconds - offset;
            
            # Ensure times don't go negative
            new_start_seconds = max( 0.0, new_start_seconds );
            new_end_seconds = max( new_start_seconds + 0.1, new_end_seconds );  # Ensure end > start
            
            # Convert back to pysrt time format
            def seconds_to_pysrt_time( seconds ):
                hours = int( seconds // 3600 );
                minutes = int( ( seconds % 3600 ) // 60 );
                secs = int( seconds % 60 );
                millisecs = int( ( seconds % 1 ) * 1000 );
                return pysrt.SubRipTime( hours, minutes, secs, millisecs );
            
            # Update subtitle timing
            old_start = sub.start;
            old_end = sub.end;
            
            sub.start = seconds_to_pysrt_time( new_start_seconds );
            sub.end = seconds_to_pysrt_time( new_end_seconds );
            
            corrections_applied += 1;
            
            if corrections_applied <= 3:  # Log first few corrections
                self.logger.debug( f"Subtitle {sub.index}: " \
                                 f"{old_start} -> {sub.start} " \
                                 f"(offset: {offset:.1f}s)" );
        
        self.logger.info( f"Applied corrections to {corrections_applied} subtitle entries" );
        
        # Generate output filename
        output_file = subtitle_file.parent / f"{subtitle_file.stem}.corrected{subtitle_file.suffix}";
        
        if not dry_run:
            # Create backup first
            backup_file = self.create_backup( subtitle_file );
            
            # Save corrected subtitle file
            subs.save( str( output_file ), encoding='utf-8' );
            self.logger.info( f"Saved corrected subtitles: {output_file}" );
            
        else:
            self.logger.info( f"Dry run: Would save corrected subtitles to {output_file}" );
        
        return output_file;
    
    def get_offset_stats( self ) -> dict:
        """Get statistics about calculated offsets."""
        if not self.offsets:
            return {};
        
        offset_values = [ offset for _, offset in self.offsets ];
        
        stats = {
            'num_offset_points': len( self.offsets ),
            'min_offset': min( offset_values ),
            'max_offset': max( offset_values ),
            'avg_offset': sum( offset_values ) / len( offset_values ),
            'offset_range': max( offset_values ) - min( offset_values )
        };
        
        return stats;
    
    def display_offset_summary( self ):
        """Display summary of calculated offsets."""
        if not self.offsets:
            self.logger.warning( "No offsets to display" );
            return;
        
        self.logger.info( "\n=== OFFSET SUMMARY ===" );
        
        stats = self.get_offset_stats();
        
        self.logger.info( f"Offset points: {stats['num_offset_points']}" );
        self.logger.info( f"Average offset: {stats['avg_offset']:.1f}s" );
        self.logger.info( f"Offset range: {stats['min_offset']:.1f}s to {stats['max_offset']:.1f}s" );
        
        self.logger.info( "\nDetailed offset points:" );
        for i, ( timestamp, offset ) in enumerate( self.offsets ):
            direction = "ahead" if offset > 0 else "behind";
            self.logger.info( f"  {i+1}. {timestamp/60:.1f}m: {abs( offset ):.1f}s {direction}" );
