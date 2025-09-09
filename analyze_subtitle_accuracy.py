#!/usr/bin/env python3
"""
Analyze subtitle synchronization accuracy by comparing original vs modified vs corrected files.

This script provides detailed analysis of timing differences and accuracy metrics.
"""
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple
import statistics


class SubtitleEntry:
    """Represents a single subtitle entry with timing and text."""
    
    def __init__( self, index: int, start_time: str, end_time: str, text: str ):
        self.index = index;
        self.start_time = start_time;
        self.end_time = end_time;
        self.text = text.strip();
        
        # Convert times to seconds for calculations
        self.start_seconds = self.time_to_seconds( start_time );
        self.end_seconds = self.time_to_seconds( end_time );
    
    def time_to_seconds( self, time_str: str ) -> float:
        """Convert SRT time format to seconds."""
        parts = time_str.replace( ',', '.' ).split( ':' );
        hours = int( parts[0] );
        minutes = int( parts[1] );
        seconds = float( parts[2] );
        return hours * 3600 + minutes * 60 + seconds;
    
    def seconds_to_time( self, seconds: float ) -> str:
        """Convert seconds back to SRT time format."""
        hours = int( seconds // 3600 );
        minutes = int( (seconds % 3600) // 60 );
        secs = seconds % 60;
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace( '.', ',' );
    
    def __repr__( self ):
        return f"SubtitleEntry({self.index}, {self.start_time}->{self.end_time}, '{self.text[:30]}...')";


class SubtitleAnalyzer:
    """Analyzer for comparing subtitle file timing accuracy."""
    
    def __init__( self ):
        self.original_entries = [];
        self.modified_entries = [];
        self.corrected_entries = [];
    
    def parse_srt_file( self, file_path: Path ) -> List[SubtitleEntry]:
        """Parse an SRT file into SubtitleEntry objects."""
        entries = [];
        
        if not file_path.exists():
            print( f"Warning: File not found: {file_path}" );
            return entries;
        
        with open( file_path, 'r', encoding='utf-8' ) as f:
            content = f.read().strip();
        
        # Split by double newline to get subtitle blocks
        blocks = re.split( r'\n\s*\n', content );
        
        for block in blocks:
            lines = block.strip().split( '\n' );
            if len( lines ) >= 3:
                try:
                    index = int( lines[0] );
                    timing = lines[1];
                    text = '\n'.join( lines[2:] );
                    
                    # Parse timing
                    time_match = re.match( r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', timing );
                    if time_match:
                        start_time = time_match.group( 1 );
                        end_time = time_match.group( 2 );
                        entries.append( SubtitleEntry( index, start_time, end_time, text ) );
                except ValueError:
                    continue;  # Skip malformed entries
        
        return entries;
    
    def load_subtitle_files( self, original_path: Path, modified_path: Path, corrected_path: Path = None ):
        """Load all subtitle files for comparison."""
        print( f"Loading subtitle files for analysis..." );
        
        self.original_entries = self.parse_srt_file( original_path );
        print( f"✓ Original: {len( self.original_entries )} entries" );
        
        self.modified_entries = self.parse_srt_file( modified_path );
        print( f"✓ Modified: {len( self.modified_entries )} entries" );
        
        if corrected_path and corrected_path.exists():
            self.corrected_entries = self.parse_srt_file( corrected_path );
            print( f"✓ Corrected: {len( self.corrected_entries )} entries" );
        else:
            print( f"⚠ Corrected file not found - will simulate ideal correction" );
            self.corrected_entries = self.simulate_ideal_correction();
            print( f"✓ Simulated ideal correction: {len( self.corrected_entries )} entries" );
    
    def simulate_ideal_correction( self ) -> List[SubtitleEntry]:
        """Simulate ideal correction by subtracting the 5-second offset from modified entries."""
        corrected = [];
        
        for entry in self.modified_entries:
            # Subtract 5 seconds to get back to original timing
            new_start = entry.start_seconds - 5.0;
            new_end = entry.end_seconds - 5.0;
            
            # Ensure no negative times
            new_start = max( 0.0, new_start );
            new_end = max( new_start + 0.1, new_end );  # Minimum duration
            
            corrected.append( SubtitleEntry(
                entry.index,
                entry.seconds_to_time( new_start ),
                entry.seconds_to_time( new_end ),
                entry.text
            ) );
        
        return corrected;
    
    def calculate_timing_differences( self ) -> Dict:
        """Calculate detailed timing difference statistics."""
        print( f"\\n=== TIMING DIFFERENCE ANALYSIS ===" );
        
        results = {
            'original_vs_modified': [],
            'original_vs_corrected': [],
            'modified_vs_corrected': []
        };
        
        # Compare original vs modified (should be +5.0 seconds)
        for orig, mod in zip( self.original_entries, self.modified_entries ):
            if orig.text.strip() == mod.text.strip():  # Same content
                start_diff = mod.start_seconds - orig.start_seconds;
                end_diff = mod.end_seconds - orig.end_seconds;
                results['original_vs_modified'].append( ( start_diff, end_diff ) );
        
        # Compare original vs corrected (should be ~0.0 seconds)
        for orig, corr in zip( self.original_entries, self.corrected_entries ):
            if orig.text.strip() == corr.text.strip():  # Same content
                start_diff = corr.start_seconds - orig.start_seconds;
                end_diff = corr.end_seconds - orig.end_seconds;
                results['original_vs_corrected'].append( ( start_diff, end_diff ) );
        
        # Compare modified vs corrected (should be -5.0 seconds)
        for mod, corr in zip( self.modified_entries, self.corrected_entries ):
            if mod.text.strip() == corr.text.strip():  # Same content
                start_diff = corr.start_seconds - mod.start_seconds;
                end_diff = corr.end_seconds - mod.end_seconds;
                results['modified_vs_corrected'].append( ( start_diff, end_diff ) );
        
        return results;
    
    def analyze_accuracy( self, differences: Dict ) -> Dict:
        """Analyze correction accuracy from timing differences."""
        print( f"\\n=== ACCURACY ANALYSIS ===" );
        
        accuracy_metrics = {};
        
        for comparison, diffs in differences.items():
            if not diffs:
                print( f"{comparison}: No matching entries found" );
                continue;
            
            start_diffs = [ d[0] for d in diffs ];
            end_diffs = [ d[1] for d in diffs ];
            
            metrics = {
                'count': len( diffs ),
                'start_mean': statistics.mean( start_diffs ),
                'start_std': statistics.stdev( start_diffs ) if len( start_diffs ) > 1 else 0,
                'start_median': statistics.median( start_diffs ),
                'end_mean': statistics.mean( end_diffs ),
                'end_std': statistics.stdev( end_diffs ) if len( end_diffs ) > 1 else 0,
                'end_median': statistics.median( end_diffs ),
                'start_range': ( min( start_diffs ), max( start_diffs ) ),
                'end_range': ( min( end_diffs ), max( end_diffs ) )
            };
            
            accuracy_metrics[comparison] = metrics;
            
            print( f"\\n{comparison.replace('_', ' ').title()}:" );
            print( f"  Samples: {metrics['count']}" );
            print( f"  Start time differences (seconds):" );
            print( f"    Mean: {metrics['start_mean']:+.3f} ± {metrics['start_std']:.3f}" );
            print( f"    Median: {metrics['start_median']:+.3f}" );
            print( f"    Range: {metrics['start_range'][0]:+.3f} to {metrics['start_range'][1]:+.3f}" );
            print( f"  End time differences (seconds):" );
            print( f"    Mean: {metrics['end_mean']:+.3f} ± {metrics['end_std']:.3f}" );
            print( f"    Median: {metrics['end_median']:+.3f}" );
            print( f"    Range: {metrics['end_range'][0]:+.3f} to {metrics['end_range'][1]:+.3f}" );
        
        return accuracy_metrics;
    
    def assess_correction_quality( self, accuracy_metrics: Dict ):
        """Assess the quality of correction based on accuracy metrics."""
        print( f"\\n=== CORRECTION QUALITY ASSESSMENT ===" );
        
        if 'original_vs_corrected' not in accuracy_metrics:
            print( "Cannot assess correction quality - no corrected file data" );
            return;
        
        corrected_metrics = accuracy_metrics['original_vs_corrected'];
        
        # Perfect correction would have mean ~0.0 and low standard deviation
        start_accuracy = abs( corrected_metrics['start_mean'] );
        start_precision = corrected_metrics['start_std'];
        
        end_accuracy = abs( corrected_metrics['end_mean'] );
        end_precision = corrected_metrics['end_std'];
        
        print( f"Start time correction:" );
        print( f"  Accuracy (deviation from 0): {start_accuracy:.3f}s" );
        print( f"  Precision (consistency): {start_precision:.3f}s" );
        
        print( f"End time correction:" );
        print( f"  Accuracy (deviation from 0): {end_accuracy:.3f}s" );
        print( f"  Precision (consistency): {end_precision:.3f}s" );
        
        # Grade the correction
        if start_accuracy < 0.1 and start_precision < 0.1:
            grade = "Excellent";
        elif start_accuracy < 0.5 and start_precision < 0.5:
            grade = "Good";
        elif start_accuracy < 1.0 and start_precision < 1.0:
            grade = "Fair";
        else:
            grade = "Poor";
        
        print( f"\\nOverall correction quality: {grade}" );
        
        return grade;
    
    def generate_recommendations( self, accuracy_metrics: Dict, grade: str ):
        """Generate recommendations for improving accuracy."""
        print( f"\\n=== RECOMMENDATIONS ===" );
        
        if grade == "Excellent":
            print( "✓ Correction quality is excellent! No changes needed." );
            return;
        
        print( f"Current correction grade: {grade}" );
        print( f"\\nTo improve accuracy, consider:" );
        
        if 'original_vs_corrected' in accuracy_metrics:
            metrics = accuracy_metrics['original_vs_corrected'];
            
            if abs( metrics['start_mean'] ) > 0.5:
                print( f"- Large systematic offset detected ({metrics['start_mean']:+.3f}s)" );
                print( f"  → Adjust base timing correction by {-metrics['start_mean']:.3f}s" );
            
            if metrics['start_std'] > 0.5:
                print( f"- High timing variance detected (±{metrics['start_std']:.3f}s)" );
                print( f"  → Increase number of audio samples (current: default 4, try 8-12)" );
                print( f"  → Lower similarity threshold (current: 0.7, try 0.6)" );
                print( f"  → Increase search window (current: 20min, try 30min)" );
        
        print( f"\\nSubShift parameter suggestions:" );
        print( f"  --samples 8 --similarity-threshold 0.6 --search-window 30" );


def main():
    """Main analysis function."""
    if len( sys.argv ) < 3:
        print( "Usage: python3 analyze_subtitle_accuracy.py original.srt modified.srt [corrected.srt]" );
        print( "If corrected.srt is not provided, ideal correction will be simulated" );
        sys.exit( 1 );
    
    original_path = Path( sys.argv[1] );
    modified_path = Path( sys.argv[2] );
    corrected_path = Path( sys.argv[3] ) if len( sys.argv ) > 3 else None;
    
    print( f"SubShift Accuracy Analysis Tool" );
    print( f"===============================" );
    
    analyzer = SubtitleAnalyzer();
    
    try:
        # Load files
        analyzer.load_subtitle_files( original_path, modified_path, corrected_path );
        
        # Calculate differences
        differences = analyzer.calculate_timing_differences();
        
        # Analyze accuracy
        accuracy_metrics = analyzer.analyze_accuracy( differences );
        
        # Assess quality
        grade = analyzer.assess_correction_quality( accuracy_metrics );
        
        # Generate recommendations
        analyzer.generate_recommendations( accuracy_metrics, grade );
        
        print( f"\\n=== ANALYSIS COMPLETE ===" );
        
    except Exception as e:
        print( f"Error during analysis: {e}" );
        import traceback;
        traceback.print_exc();
        sys.exit( 1 );


if __name__ == "__main__":
    main();
