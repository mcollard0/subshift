#!/usr/bin/env python3
"""
Demo script to test the weighted offset calculation functionality.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert( 0, str( Path( __file__ ).parent / "src" ) );

from subshift.align import AlignmentMatch;
from subshift.offset import OffsetCalculator;
from subshift.logging import get_logger;

def create_demo_matches():
    """Create demo alignment matches with different similarity scores and offsets."""
    
    # Simulate scenario where we have various matches with different quality
    # High similarity match shows +30s offset (subtitles ahead)
    match1 = AlignmentMatch(
        audio_sample_index=0,
        audio_sample_timestamp=120.0,  # 2 minutes
        audio_text="Hello robot, how are you doing today?",
        subtitle_minute=2,
        subtitle_timestamp=150.0,  # Should be 120s, but is at 150s (+30s offset)
        subtitle_text="Hello robot, how are you doing today?",
        levenshtein_distance=2,
        similarity_score=0.95,  # Very high similarity
        is_match=True
    );
    
    # Medium similarity match shows +29s offset (consistent)
    match2 = AlignmentMatch(
        audio_sample_index=1, 
        audio_sample_timestamp=300.0,  # 5 minutes
        audio_text="What a beautiful day for adventure",
        subtitle_minute=5,
        subtitle_timestamp=329.0,  # Should be 300s, but is at 329s (+29s offset)
        subtitle_text="What a lovely day for exploration",
        levenshtein_distance=8,
        similarity_score=0.75,  # Medium similarity
        is_match=True
    );
    
    # Lower similarity match shows +25s offset (slightly different, could be noise)
    match3 = AlignmentMatch(
        audio_sample_index=2,
        audio_sample_timestamp=480.0,  # 8 minutes
        audio_text="Time to go home now",
        subtitle_minute=8,
        subtitle_timestamp=505.0,  # Should be 480s, but is at 505s (+25s offset)
        subtitle_text="Time to return home",
        levenshtein_distance=12,
        similarity_score=0.65,  # Lower similarity
        is_match=True
    );
    
    # High similarity match shows +31s offset (consistent with main trend)
    match4 = AlignmentMatch(
        audio_sample_index=3,
        audio_sample_timestamp=660.0,  # 11 minutes
        audio_text="Thank you for the adventure",
        subtitle_minute=11,
        subtitle_timestamp=691.0,  # Should be 660s, but is at 691s (+31s offset)
        subtitle_text="Thank you for this adventure",
        levenshtein_distance=3,
        similarity_score=0.88,  # High similarity
        is_match=True
    );
    
    return [ match1, match2, match3, match4 ];

def test_weighted_offset_calculation():
    """Test the weighted offset calculation system."""
    
    logger = get_logger();
    logger.info( "=== TESTING WEIGHTED OFFSET CALCULATION ===" );
    
    # Create demo matches
    matches = create_demo_matches();
    
    logger.info( f"\\nCreated {len( matches )} demo alignment matches:" );
    for match in matches:
        offset = match.subtitle_timestamp - match.audio_sample_timestamp;
        logger.info( f"  Match {match.audio_sample_index}: similarity={match.similarity_score:.3f}, offset={offset:.1f}s" );
    
    # Test offset calculation
    calculator = OffsetCalculator();
    offsets = calculator.calculate_sample_offsets( matches );
    
    logger.info( f"\\nCalculated {len( offsets )} offset points:" );
    for timestamp, offset in offsets:
        logger.info( f"  {timestamp/60:.1f}m: {offset:.1f}s" );
    
    # Test uniform weighted correction
    logger.info( f"\\n=== UNIFORM WEIGHTED CORRECTION TEST ===" );
    
    should_use_uniform = calculator.should_use_uniform_correction( matches );
    logger.info( f"Should use uniform correction: {should_use_uniform}" );
    
    if should_use_uniform:
        uniform_offset = calculator.apply_uniform_weighted_offset( matches );
        logger.info( f"Uniform weighted offset: {uniform_offset:.1f}s" );
    else:
        logger.info( "Would use interpolated correction instead" );
    
    # Calculate manual weighted average for comparison
    logger.info( f"\\n=== MANUAL VERIFICATION ===" );
    
    weighted_sum = 0.0;
    total_weight = 0.0;
    simple_sum = 0.0;
    
    for match in matches:
        offset = match.subtitle_timestamp - match.audio_sample_timestamp;
        weight = match.similarity_score;
        
        weighted_sum += offset * weight;
        total_weight += weight;
        simple_sum += offset;
        
        logger.info( f"  Match {match.audio_sample_index}: offset={offset:.1f}s * weight={weight:.3f} = {offset*weight:.3f}" );
    
    manual_weighted_avg = weighted_sum / total_weight;
    simple_avg = simple_sum / len( matches );
    
    logger.info( f"\\nManual calculation:" );
    logger.info( f"  Simple average: {simple_avg:.1f}s" );
    logger.info( f"  Weighted average: {manual_weighted_avg:.1f}s" );
    logger.info( f"  Total weight: {total_weight:.3f}" );
    
    # Show the difference
    weight_benefit = abs( manual_weighted_avg - simple_avg );
    logger.info( f"\\nWeighted approach adjusts by {weight_benefit:.1f}s compared to simple average" );
    
    if manual_weighted_avg > simple_avg:
        logger.info( "Weighted average gives more positive offset (trusts high-similarity matches more)" );
    else:
        logger.info( "Weighted average gives more negative offset (trusts high-similarity matches more)" );

if __name__ == "__main__":
    test_weighted_offset_calculation();
