#!/usr/bin/env python3
"""
Demo script to test adaptive similarity threshold adjustment for challenging content.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert( 0, str( Path( __file__ ).parent / "src" ) );

from subshift.sync import SubtitleSynchronizer;
from subshift.logging import get_logger;

def test_adaptive_threshold_logic():
    """Test the adaptive threshold calculation logic."""
    
    logger = get_logger();
    logger.info( "=== TESTING ADAPTIVE SIMILARITY THRESHOLD ===" );
    
    # Create a mock synchronizer to test the adaptive threshold method
    class MockSynchronizer:
        def __init__( self ):
            self.logger = get_logger();
        
        def _get_adaptive_threshold( self, current_threshold: float, sample_count: int ) -> float:
            # Copy the method from SubtitleSynchronizer for testing
            if current_threshold >= 0.75:  # High threshold - try moderate reduction
                adaptive_threshold = 0.6;  # Reduce to 60% for first attempt
            elif current_threshold >= 0.65:  # Medium threshold - try significant reduction
                adaptive_threshold = 0.5;  # Reduce to 50% for complex content (WALL-E level)
            elif current_threshold >= 0.55:  # Already low - try minimal reduction
                adaptive_threshold = 0.45; # Final fallback for very challenging content
            else:
                # Already very low - no further adaptation recommended
                return current_threshold;
            
            # Additional adjustment based on sample count
            # More samples with no matches = increase difficulty assessment
            if sample_count >= 20:  # Large sample count with no matches = very challenging
                adaptive_threshold = max( 0.4, adaptive_threshold - 0.1 );
            elif sample_count >= 10:  # Moderate sample count = somewhat challenging
                adaptive_threshold = max( 0.45, adaptive_threshold - 0.05 );
            
            # Never go below minimum viable threshold
            adaptive_threshold = max( 0.4, adaptive_threshold );
            
            return adaptive_threshold;
    
    sync = MockSynchronizer();
    
    logger.info( f"\\n=== ADAPTIVE THRESHOLD SCENARIOS ===" );
    
    # Test different threshold scenarios
    test_cases = [
        # ( description, initial_threshold, sample_count )
        ( "High threshold (80%), few samples", 0.8, 8 ),
        ( "High threshold (80%), many samples", 0.8, 24 ),
        ( "Standard threshold (70%), few samples", 0.7, 8 ),
        ( "Standard threshold (70%), many samples", 0.7, 24 ),
        ( "Default threshold (65%), few samples", 0.65, 8 ),
        ( "Default threshold (65%), many samples", 0.65, 24 ),
        ( "Low threshold (60%), few samples", 0.6, 8 ),
        ( "Low threshold (60%), many samples", 0.6, 24 ),
        ( "Very low threshold (50%), few samples", 0.5, 8 ),
        ( "Very low threshold (50%), many samples", 0.5, 24 ),
        ( "Minimal threshold (45%), many samples", 0.45, 24 ),
        ( "Bottom threshold (40%), many samples", 0.4, 24 ),
    ];
    
    for desc, initial, samples in test_cases:
        adaptive = sync._get_adaptive_threshold( initial, samples );
        reduction = initial - adaptive;
        
        if reduction > 0:
            logger.info( f"  {desc:40}: {initial:.2f} -> {adaptive:.2f} (-{reduction:.2f})" );
        else:
            logger.info( f"  {desc:40}: {initial:.2f} -> {adaptive:.2f} (no change)" );
    
    logger.info( f"\\n=== WALL-E SCENARIO SIMULATION ===" );
    
    # Simulate WALL-E scenario: Start with 70%, no matches, adapt to 50%
    wall_e_scenarios = [
        ( "Initial attempt (default)", 0.7, 16 ),
        ( "WALL-E complex audio", 0.65, 16 ),
        ( "Very challenging content", 0.6, 20 ),
        ( "Extremely difficult", 0.5, 24 ),
    ];
    
    for desc, threshold, samples in wall_e_scenarios:
        adaptive = sync._get_adaptive_threshold( threshold, samples );
        
        # Expected match types at different thresholds
        expected_results = {
            0.7: "Clean dialogue only",
            0.65: "Most dialogue, some noise",  
            0.6: "Dialogue + background speech",
            0.5: "Complex audio (WALL-E level)",
            0.45: "Very noisy/distorted content",
            0.4: "Minimal viable matching"
        };
        
        expected = expected_results.get( adaptive, "Unknown" );
        
        logger.info( f"  {desc:25}: {threshold:.2f} -> {adaptive:.2f} ({expected})" );
    
    logger.info( f"\\n=== CONTENT TYPE RECOMMENDATIONS ===" );
    
    content_types = [
        ( "Clean TV shows/movies", 0.75, 16 ),
        ( "Standard dialogue content", 0.7, 16 ),
        ( "Music-heavy content", 0.65, 20 ),
        ( "Animated films (WALL-E)", 0.65, 24 ),
        ( "Foreign films (accents)", 0.6, 20 ),
        ( "Action movies (explosions)", 0.6, 24 ),
        ( "Documentary (varied audio)", 0.55, 20 ),
        ( "Concert/live performance", 0.5, 24 ),
    ];
    
    for content_type, initial_threshold, typical_samples in content_types:
        adaptive = sync._get_adaptive_threshold( initial_threshold, typical_samples );
        
        improvement = "significantly" if initial_threshold - adaptive >= 0.1 else "moderately" if initial_threshold - adaptive >= 0.05 else "minimally";
        
        logger.info( f"  {content_type:25}: {initial_threshold:.2f} -> {adaptive:.2f} ({improvement} adapted)" );

def test_threshold_progression():
    """Test the progressive threshold reduction strategy."""
    
    logger = get_logger();
    logger.info( f"\\n=== PROGRESSIVE THRESHOLD STRATEGY ===" );
    
    # Simulate progressive attempts for very challenging content
    sync = SubtitleSynchronizer(
        video_file=Path( "/fake/video.mp4" ),  # Won't be used in this test
        subtitle_file=Path( "/fake/subtitles.srt" )  # Won't be used in this test
    );
    
    initial_threshold = 0.8;
    sample_count = 20;
    
    logger.info( f"Simulating progressive adaptation for challenging content:" );
    logger.info( f"Initial setup: {initial_threshold:.1%} threshold, {sample_count} samples" );
    
    current_threshold = initial_threshold;
    attempt = 1;
    
    while attempt <= 4:  # Max 4 adaptation attempts
        adaptive_threshold = sync._get_adaptive_threshold( current_threshold, sample_count );
        
        if adaptive_threshold >= current_threshold:
            logger.info( f"  Attempt {attempt}: No further adaptation possible at {current_threshold:.1%}" );
            break;
        
        reduction = current_threshold - adaptive_threshold;
        logger.info( f"  Attempt {attempt}: {current_threshold:.1%} -> {adaptive_threshold:.1%} (-{reduction:.1%})" );
        
        current_threshold = adaptive_threshold;
        attempt += 1;
        
        # In real scenario, would stop here if matches found
        if adaptive_threshold <= 0.4:  # Reached minimum
            logger.info( f"  Reached minimum viable threshold: {adaptive_threshold:.1%}" );
            break;
    
    logger.info( f"\\n=== EXPECTED OUTCOMES ===" );
    logger.info( f"  0.80-0.70: Only perfect/near-perfect matches" );
    logger.info( f"  0.65-0.60: Standard content, good dialogue" );
    logger.info( f"  0.55-0.50: Complex content (WALL-E, animated, music)" );
    logger.info( f"  0.45-0.40: Very challenging (accents, noise, effects)" );
    logger.info( f"  Below 0.40: Too permissive, high false positive risk" );

if __name__ == "__main__":
    test_adaptive_threshold_logic();
    test_threshold_progression();
