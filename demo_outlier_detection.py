#!/usr/bin/env python3
"""
Demo script to test outlier detection for the WALL-E scenario.
Tests filtering of the 6.8s outlier when true offset is ~30s.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert( 0, str( Path( __file__ ).parent / "src" ) );

from subshift.align import AlignmentMatch;
from subshift.offset import OffsetCalculator;
from subshift.logging import get_logger;

def create_wall_e_scenario():
    """Create demo matches simulating the WALL-E offset detection scenario."""
    
    # Simulate WALL-E scenario: +30s true offset with one bad 6.8s detection
    
    # Good match: Detects full +30s offset with decent similarity
    match1 = AlignmentMatch(
        audio_sample_index=0,
        audio_sample_timestamp=120.0,  # 2 minutes
        audio_text="EVE, directive?",
        subtitle_minute=2,
        subtitle_timestamp=150.3,  # +30.3s offset (close to true +30s)
        subtitle_text="EVE. Directive?",
        levenshtein_distance=1,
        similarity_score=0.72,  # Above 60% threshold
        is_match=True
    );
    
    # Bad match: Partial/noisy detection shows +6.8s offset
    match2 = AlignmentMatch(
        audio_sample_index=1,
        audio_sample_timestamp=300.0,  # 5 minutes
        audio_text="WALL-E beeping and mechanical sounds",
        subtitle_minute=5,
        subtitle_timestamp=306.8,  # +6.8s offset (outlier)
        subtitle_text="[mechanical whirring]",
        levenshtein_distance=25,
        similarity_score=0.61,  # Just above threshold
        is_match=True
    );
    
    # Another good match: Confirms +29s offset trend
    match3 = AlignmentMatch(
        audio_sample_index=2,
        audio_sample_timestamp=480.0,  # 8 minutes
        audio_text="Auto, directive Alpha",
        subtitle_minute=8,
        subtitle_timestamp=509.2,  # +29.2s offset
        subtitle_text="AUTO. Directive: Alpha.",
        levenshtein_distance=4,
        similarity_score=0.78,  # Good similarity
        is_match=True
    );
    
    # High confidence match: Strong +31s detection
    match4 = AlignmentMatch(
        audio_sample_index=3,
        audio_sample_timestamp=660.0,  # 11 minutes
        audio_text="Earth, define dancing",
        subtitle_minute=11,
        subtitle_timestamp=691.1,  # +31.1s offset
        subtitle_text="Earth. Define: Dancing.",
        levenshtein_distance=2,
        similarity_score=0.85,  # High similarity
        is_match=True
    );
    
    return [ match1, match2, match3, match4 ];

def test_outlier_filtering():
    """Test outlier detection for the WALL-E scenario."""
    
    logger = get_logger();
    logger.info( "=== TESTING OUTLIER DETECTION (WALL-E SCENARIO) ===" );
    
    # Create scenario with 6.8s outlier among 30s+ offsets
    matches = create_wall_e_scenario();
    
    logger.info( f"\\nScenario: 4 matches with 1 outlier (6.8s among ~30s offsets)" );
    for match in matches:
        offset = match.subtitle_timestamp - match.audio_sample_timestamp;
        logger.info( f"  Match {match.audio_sample_index}: similarity={match.similarity_score:.3f}, offset={offset:.1f}s" );
    
    # Test offset calculation WITHOUT outlier filtering
    logger.info( f"\\n=== WITHOUT OUTLIER FILTERING ===" );
    calculator_no_filter = OffsetCalculator();
    calculator_no_filter._filter_offset_outliers = lambda x, method='iqr': x;  # Disable filtering
    
    offsets_no_filter = calculator_no_filter.calculate_sample_offsets( matches );
    raw_offsets = [ offset for _, offset in offsets_no_filter ];
    simple_avg_no_filter = sum( raw_offsets ) / len( raw_offsets );
    
    logger.info( f"Raw offsets: {[ f'{offset:.1f}s' for offset in raw_offsets ]}" );
    logger.info( f"Simple average: {simple_avg_no_filter:.1f}s" );
    
    # Test offset calculation WITH outlier filtering
    logger.info( f"\n=== WITH OUTLIER FILTERING ===" );
    calculator_with_filter = OffsetCalculator();
    
    offsets_with_filter = calculator_with_filter.calculate_sample_offsets( matches );
    filtered_offsets = [ offset for _, offset in offsets_with_filter ];
    simple_avg_with_filter = sum( filtered_offsets ) / len( filtered_offsets );
    
    logger.info( f"Filtered offsets: {[ f'{offset:.1f}s' for offset in filtered_offsets ]}" );
    logger.info( f"Simple average after filtering: {simple_avg_with_filter:.1f}s" );
    
    # Show the improvement
    improvement = abs( simple_avg_with_filter - 30.0 ) - abs( simple_avg_no_filter - 30.0 );
    logger.info( f"\n=== FILTERING EFFECTIVENESS ===" );
    logger.info( f"True offset: 30.0s (target)" );
    logger.info( f"Without filtering: {simple_avg_no_filter:.1f}s (error: {abs(simple_avg_no_filter - 30.0):.1f}s)" );
    logger.info( f"With filtering: {simple_avg_with_filter:.1f}s (error: {abs(simple_avg_with_filter - 30.0):.1f}s)" );
    
    if improvement < 0:
        logger.info( f"✓ Filtering improved accuracy by {abs(improvement):.1f}s" );
    else:
        logger.info( f"✗ Filtering worsened accuracy by {improvement:.1f}s" );
    
    # Test weighted uniform correction
    logger.info( f"\n=== WEIGHTED UNIFORM CORRECTION ===" );
    should_use_uniform = calculator_with_filter.should_use_uniform_correction( matches );
    logger.info( f"Should use uniform correction: {should_use_uniform}" );
    
    if should_use_uniform:
        uniform_offset = calculator_with_filter.apply_uniform_weighted_offset( matches );
        logger.info( f"Weighted uniform offset: {uniform_offset:.1f}s (error: {abs(uniform_offset - 30.0):.1f}s)" );
    
    # Test different outlier methods
    logger.info( f"\n=== OUTLIER DETECTION METHODS ===" );
    
    test_offsets = [ ( 120.0, 30.3 ), ( 300.0, 6.8 ), ( 480.0, 29.2 ), ( 660.0, 31.1 ) ];
    
    for method in [ "adaptive", "iqr", "zscore" ]:
        logger.info( f"\nTesting {method.upper()} method:" );
        filtered = calculator_with_filter._filter_offset_outliers( test_offsets, method=method );
        filtered_values = [ offset for _, offset in filtered ];
        logger.info( f"  Kept {len( filtered )}/{len( test_offsets )} points: {[ f'{v:.1f}s' for v in filtered_values ]}" );
        
        if len( filtered ) > 0:
            filtered_avg = sum( filtered_values ) / len( filtered_values );
            logger.info( f"  Filtered average: {filtered_avg:.1f}s (error: {abs(filtered_avg - 30.0):.1f}s)" );

if __name__ == "__main__":
    test_outlier_filtering();
