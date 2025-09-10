"""
Offset calculation and subtitle correction module.
"""
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
import pysrt
import statistics

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
        Calculate time offsets from successful alignment matches with weighted averaging.
        
        Offset = subtitle_timestamp - audio_sample_timestamp
        Positive offset means subtitles are ahead (need to be delayed)
        Negative offset means subtitles are behind (need to be advanced)
        
        Uses similarity scores to weight offsets - higher similarity matches
        have more influence on the final correction.
        
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
        raw_offsets = [];
        total_weight = 0.0;
        weighted_sum = 0.0;
        
        for match in successful_matches:
            # Calculate offset: subtitle time - audio time
            offset = match.subtitle_timestamp - match.audio_sample_timestamp;
            weight = match.similarity_score;  # Use similarity as weight
            
            self.offsets.append( ( match.audio_sample_timestamp, offset ) );
            raw_offsets.append( offset );
            
            # Accumulate for weighted average
            weighted_sum += offset * weight;
            total_weight += weight;
            
            self.logger.debug( f"Sample {match.audio_sample_index}: " \
                             f"audio={match.audio_sample_timestamp/60:.1f}m, " \
                             f"subtitle={match.subtitle_timestamp/60:.1f}m, " \
                             f"offset={offset:.1f}s, weight={weight:.3f}" );
        
        # Calculate weighted average offset
        if total_weight > 0:
            weighted_avg_offset = weighted_sum / total_weight;
            simple_avg_offset = sum( raw_offsets ) / len( raw_offsets );
            
            self.logger.info( f"Offset calculation: Simple avg={simple_avg_offset:.1f}s, " \
                            f"Weighted avg={weighted_avg_offset:.1f}s " \
                            f"(total weight: {total_weight:.2f})" );
            
            # For now, we'll still use individual offsets for interpolation,
            # but the weighted average shows the overall correction tendency
            # Future enhancement: could apply uniform weighted average if offsets are consistent
        
        # Apply outlier filtering if we have enough data points
        if len( self.offsets ) >= 3:
            filtered_offsets = self._filter_offset_outliers( self.offsets );
            if filtered_offsets:
                self.offsets = filtered_offsets;
                self.logger.info( f"Filtered {len(raw_offsets) - len(self.offsets)} outlier offset(s)" );
        
        # Sort by timestamp for interpolation
        self.offsets.sort( key=lambda x: x[0] );
        
        self.logger.info( f"Calculated {len( self.offsets )} offset points" );
        return self.offsets;
    
    def apply_uniform_weighted_offset( self, matches: List[AlignmentMatch] ) -> float:
        """
        Calculate a single uniform offset using weighted average of all matches.
        
        This is useful when all matches indicate a consistent timing shift,
        where a single global correction is more appropriate than interpolation.
        
        Args:
            matches: List of AlignmentMatch objects
            
        Returns:
            Weighted average offset in seconds
        """
        successful_matches = [ match for match in matches if match.is_match ];
        
        if not successful_matches:
            return 0.0;
        
        weighted_sum = 0.0;
        total_weight = 0.0;
        
        for match in successful_matches:
            offset = match.subtitle_timestamp - match.audio_sample_timestamp;
            weight = match.similarity_score;
            
            weighted_sum += offset * weight;
            total_weight += weight;
        
        if total_weight > 0:
            return weighted_sum / total_weight;
        else:
            return 0.0;
    
    def should_use_uniform_correction( self, matches: List[AlignmentMatch], variance_threshold: float = 5.0 ) -> bool:
        """
        Determine if uniform correction should be used instead of interpolation.
        
        Uniform correction is preferred when:
        1. All offsets are relatively consistent (low variance)
        2. We have multiple high-quality matches
        
        Args:
            matches: List of AlignmentMatch objects
            variance_threshold: Maximum variance in seconds to consider uniform
            
        Returns:
            True if uniform correction should be used
        """
        successful_matches = [ match for match in matches if match.is_match ];
        
        if len( successful_matches ) < 2:
            return False;  # Need multiple matches for variance calculation
        
        # Calculate offset variance
        offsets = [ match.subtitle_timestamp - match.audio_sample_timestamp for match in successful_matches ];
        
        if len( offsets ) < 2:
            return False;
        
        mean_offset = sum( offsets ) / len( offsets );
        variance = sum( ( offset - mean_offset ) ** 2 for offset in offsets ) / len( offsets );
        std_dev = variance ** 0.5;
        
        # Also check if we have good quality matches
        avg_similarity = sum( match.similarity_score for match in successful_matches ) / len( successful_matches );
        
        is_consistent = std_dev <= variance_threshold;
        is_high_quality = avg_similarity >= 0.75;  # At least 75% average similarity
        
        self.logger.debug( f"Uniform correction check: std_dev={std_dev:.1f}s, " \
                         f"avg_similarity={avg_similarity:.3f}, " \
                         f"consistent={is_consistent}, high_quality={is_high_quality}" );
        
        return is_consistent and is_high_quality;
    
    def _filter_offset_outliers( self, offset_points: List[Tuple[float, float]], method: str = "adaptive" ) -> List[Tuple[float, float]]:
        """
        Filter statistical outliers from offset points.
        
        Uses domain-aware outlier detection optimized for subtitle synchronization.
        For small datasets (< 6 points), uses more aggressive thresholds.
        
        Args:
            offset_points: List of (timestamp, offset) tuples
            method: "iqr" (default), "zscore", or "adaptive" for outlier detection
            
        Returns:
            Filtered list of offset points with outliers removed
        """
        if len( offset_points ) < 3:
            return offset_points;  # Need at least 3 points for outlier detection
        
        offsets = [ offset for _, offset in offset_points ];
        
        if method == "adaptive":
            # Adaptive method for small datasets - uses median and more aggressive thresholds
            median = statistics.median( offsets );
            
            # Calculate deviations from median
            deviations = [ abs( offset - median ) for offset in offsets ];
            
            # For small datasets, use stricter threshold based on median absolute deviation
            if len( offset_points ) <= 5:
                # Very aggressive for small datasets
                mad = statistics.median( deviations ) if len( deviations ) > 1 else 0;
                threshold = max( 3.0, 1.5 * mad );  # At least 3s threshold, or 1.5*MAD
            else:
                # Less aggressive for larger datasets  
                mad = statistics.median( deviations );
                threshold = max( 5.0, 2.0 * mad );  # At least 5s threshold, or 2*MAD
            
            lower_bound = median - threshold;
            upper_bound = median + threshold;
            
            self.logger.debug( f"Adaptive outlier bounds: [{lower_bound:.1f}s, {upper_bound:.1f}s] " \
                             f"(median={median:.1f}s, MAD={mad:.1f}s, threshold={threshold:.1f}s)" );
            
        elif method == "iqr":
            # Interquartile Range method (more robust for small datasets)
            try:
                q1 = statistics.quantiles( offsets, n=4 )[0];  # 25th percentile
                q3 = statistics.quantiles( offsets, n=4 )[2];  # 75th percentile
                iqr = q3 - q1;
                
                # Define outlier bounds (1.5 * IQR is standard)
                lower_bound = q1 - 1.5 * iqr;
                upper_bound = q3 + 1.5 * iqr;
                
                self.logger.debug( f"IQR outlier bounds: [{lower_bound:.1f}s, {upper_bound:.1f}s]" );
                
            except statistics.StatisticsError:
                # Fall back to simple method if quantiles fail
                median = statistics.median( offsets );
                mad = statistics.median( [ abs( offset - median ) for offset in offsets ] );
                
                # Use Median Absolute Deviation (MAD) with 2.5 threshold
                threshold = 2.5 * mad;
                lower_bound = median - threshold;
                upper_bound = median + threshold;
                
                self.logger.debug( f"MAD outlier bounds: [{lower_bound:.1f}s, {upper_bound:.1f}s]" );
                
        elif method == "zscore":
            # Z-score method (assumes normal distribution)
            mean_offset = statistics.mean( offsets );
            std_offset = statistics.stdev( offsets ) if len( offsets ) > 1 else 0;
            
            if std_offset == 0:
                return offset_points;  # No variation, no outliers
            
            # Z-score threshold of 2.0 (95% confidence)
            z_threshold = 2.0;
            lower_bound = mean_offset - z_threshold * std_offset;
            upper_bound = mean_offset + z_threshold * std_offset;
            
            self.logger.debug( f"Z-score outlier bounds: [{lower_bound:.1f}s, {upper_bound:.1f}s]" );
            
        else:
            raise ValueError( f"Unknown outlier detection method: {method}" );
        
        # Filter outliers
        filtered_points = [];
        outliers_detected = [];
        
        for timestamp, offset in offset_points:
            if lower_bound <= offset <= upper_bound:
                filtered_points.append( ( timestamp, offset ) );
            else:
                outliers_detected.append( ( timestamp, offset ) );
                self.logger.warning( f"Outlier detected: {timestamp/60:.1f}m = {offset:.1f}s (outside bounds)" );
        
        if outliers_detected:
            self.logger.info( f"Filtered {len( outliers_detected )} outlier(s) using {method.upper()} method" );
            
            # Log outliers for debugging
            for timestamp, offset in outliers_detected:
                self.logger.debug( f"  Removed outlier: {timestamp/60:.1f}m = {offset:.1f}s" );
        
        # Ensure we don't remove too many points
        if len( filtered_points ) < max( 1, len( offset_points ) // 2 ):
            self.logger.warning( f"Outlier filtering too aggressive, keeping original {len( offset_points )} points" );
            return offset_points;
        
        return filtered_points;
    
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
    
    def apply_corrections( self, subtitle_file: Path, matches: List[AlignmentMatch] = None, dry_run: bool = False ) -> Path:
        """
        Apply calculated offsets to subtitle file and save corrected version.
        
        Chooses between interpolated corrections or uniform weighted correction
        based on the consistency and quality of the matches.
        
        Args:
            subtitle_file: Path to original subtitle file
            matches: List of AlignmentMatch objects (for weighted uniform correction)
            dry_run: If True, don't actually save the corrected file
            
        Returns:
            Path to corrected subtitle file (or would-be path if dry_run)
        """
        if not self.offsets:
            raise ValueError( "No offsets calculated. Run calculate_sample_offsets first." );
        
        self.logger.info( f"Applying corrections to {subtitle_file}" );
        
        # Determine correction method
        use_uniform = False;
        uniform_offset = 0.0;
        
        if matches and self.should_use_uniform_correction( matches ):
            uniform_offset = self.apply_uniform_weighted_offset( matches );
            use_uniform = True;
            self.logger.info( f"Using uniform weighted correction: {uniform_offset:.1f}s offset" );
        else:
            self.logger.info( f"Using interpolated correction with {len( self.offsets )} offset points" );
        
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
            
            # Calculate offset for this subtitle
            if use_uniform:
                offset = uniform_offset;
            else:
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
