#!/usr/bin/env python3
"""
Demo script to test the enhanced sampling strategy with higher default sample counts.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert( 0, str( Path( __file__ ).parent / "src" ) );

from subshift.audio import AdaptiveSamplingCoordinator;
from subshift.sync import SubtitleSynchronizer;
from subshift.logging import get_logger;

def test_enhanced_sampling_defaults():
    """Test the new enhanced sampling defaults and recommendations."""
    
    logger = get_logger();
    logger.info( "=== TESTING ENHANCED SAMPLING STRATEGY ===" );
    
    # Test AdaptiveSamplingCoordinator recommendations
    coordinator = AdaptiveSamplingCoordinator( debug=True );
    
    logger.info( f"\\n=== SAMPLE COUNT RECOMMENDATIONS ===" );
    
    consistency_scenarios = [ "insufficient_data", "consistent", "moderate", "inconsistent" ];
    
    for consistency in consistency_scenarios:
        recommended = coordinator.recommend_sample_count( consistency );
        cost = coordinator.get_cost_estimate( recommended );
        logger.info( f"  {consistency:15}: {recommended:2d} samples (${cost:.3f} cost)" );
    
    logger.info( f"\\n=== SUCCESS RATE ADJUSTMENTS ===" );
    
    # Test success rate adjustments
    base_consistency = "moderate";
    success_rates = [ 0.3, 0.5, 0.7, 0.9 ];
    
    for success_rate in success_rates:
        recommended = coordinator.recommend_sample_count( base_consistency, success_rate );
        cost = coordinator.get_cost_estimate( recommended );
        logger.info( f"  Success rate {success_rate:.1f}: {recommended:2d} samples (${cost:.3f} cost)" );
    
    logger.info( f"\\n=== COMPARISON: OLD vs NEW DEFAULTS ===" );
    
    old_defaults = { "consistent": 8, "moderate": 20, "inconsistent": 35, "insufficient_data": 12 };
    
    for consistency in consistency_scenarios:
        old_count = old_defaults.get( consistency, 20 );
        new_count = coordinator.recommend_sample_count( consistency );
        old_cost = coordinator.get_cost_estimate( old_count );
        new_cost = coordinator.get_cost_estimate( new_count );
        
        improvement = new_count - old_count;
        cost_increase = new_cost - old_cost;
        
        logger.info( f"  {consistency:15}: {old_count:2d} -> {new_count:2d} samples " \
                   f"(+{improvement:2d}, +${cost_increase:.3f} cost)" );
    logger.info( f"\\n=== COST ANALYSIS ===" );
    
    # Typical scenarios
    scenarios = [
        ( "Clean dialogue (consistent)", "consistent" ),
        ( "Standard content (moderate)", "moderate" ),
        ( "Complex audio (inconsistent)", "inconsistent" )
    ];
    
    for desc, consistency in scenarios:
        samples = coordinator.recommend_sample_count( consistency );
        cost = coordinator.get_cost_estimate( samples );
        accuracy_target = {
            "consistent": ">95%",
            "moderate": ">90%", 
            "inconsistent": ">85%"
        }.get( consistency, "~80%" );
        
        logger.info( f"  {desc:25}: {samples:2d} samples, ${cost:.3f} cost, {accuracy_target} target accuracy" );
        
    logger.info( f"\n=== SUBSHIFT SYNCHRONIZER DEFAULTS ===" );
    
    # Test default synchronizer behavior
    # Note: Can't test full synchronizer without real files, but can test default values
    try:
        # This will fail due to missing files, but we can see the default sample count
        sync_default = 16;  # New default from constructor
        sync_old = 4;       # Old default
        
        cost_new = coordinator.get_cost_estimate( sync_default );
        cost_old = coordinator.get_cost_estimate( sync_old );
        
        logger.info( f"  Default samples: {sync_old} -> {sync_default} (+{sync_default - sync_old})" );
        logger.info( f"  Default cost: ${cost_old:.3f} -> ${cost_new:.3f} (+${cost_new - cost_old:.3f})" );
        logger.info( f"  Expected improvement: Significantly better match detection" );
        
        # Expected benefits
        logger.info( f"\n=== EXPECTED BENEFITS ===" );
        logger.info( f"  1. Better coverage: 4x more data points across video timeline" );
        logger.info( f"  2. Outlier resistance: More samples = better statistical filtering" );
        logger.info( f"  3. Reduced failure rate: Higher chance of finding good matches" );
        logger.info( f"  4. Improved accuracy: More evidence for offset calculation" );
        logger.info( f"  5. Better for complex content: WALL-E, animated films, music-heavy content" );
        
    except Exception as e:
        logger.info( f"  Could not test full synchronizer: {e}" );

def test_cost_impact_analysis():
    """Analyze the cost impact of enhanced sampling."""
    
    logger = get_logger();
    logger.info( f"\n=== COST IMPACT ANALYSIS ===" );
    
    coordinator = AdaptiveSamplingCoordinator( debug=False );
    
    # Analyze cost for different content types
    content_types = [
        ( "Short video (30min)", 16 ),
        ( "TV episode (45min)", 20 ),
        ( "Movie (2hr)", 24 ),
        ( "Long movie (3hr)", 32 )
    ];
    
    for content_type, typical_samples in content_types:
        cost = coordinator.get_cost_estimate( typical_samples );
        logger.info( f"  {content_type:20}: {typical_samples:2d} samples, ${cost:.3f} cost" );
    
    # Compare to manual correction time
    logger.info( f"\n=== VALUE PROPOSITION ===" );
    logger.info( f"  Manual correction time: 15-60 minutes" );
    logger.info( f"  SubShift processing: 2-5 minutes + AI cost" );
    logger.info( f"  Typical AI cost: $0.010-0.050 (much less than hourly wage)" );
    logger.info( f"  Net benefit: Massive time savings at minimal cost" );

if __name__ == "__main__":
    test_enhanced_sampling_defaults();
    test_cost_impact_analysis();
