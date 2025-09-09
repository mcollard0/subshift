#!/usr/bin/env python3
"""
Test individual SubShift components to verify functionality without API calls.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_subtitle_processor():
    """Test SubtitleProcessor functionality."""
    print("Testing SubtitleProcessor...")
    
    try:
        from subshift.subtitles import SubtitleProcessor
        
        # Create processor
        processor = SubtitleProcessor(min_chars=40)
        print(f"✓ SubtitleProcessor created: {type(processor)}")
        
        # Test with our modified subtitle file
        subtitle_file = Path("/media/michael/FASTESTARCHIVE/Archive/Media/The Matrix (1999)/The.Matrix.1999.Subtitles.YIFY.modified.srt")
        
        if not subtitle_file.exists():
            print(f"✗ Subtitle file not found: {subtitle_file}")
            return False
        
        # Parse subtitle file
        entries = processor.parse_subtitle_file(subtitle_file)
        print(f"✓ Parsed {len(entries)} subtitle entries")
        
        # Create minute index
        processor.create_minute_index()
        print("✓ Created minute-based index")
        
        # Get stats
        stats = processor.get_subtitle_stats()
        print(f"✓ Statistics: {stats['total_entries']} entries, {stats['duration_minutes']:.1f} minutes")
        print(f"✓ Valid minutes with ≥{processor.min_chars} chars: {stats['valid_minutes']}")
        
        return processor, len(entries)
        
    except Exception as e:
        print(f"✗ SubtitleProcessor test failed: {e}")
        import traceback
        traceback.print_exc()
        return None, 0

def test_alignment_engine():
    """Test AlignmentEngine functionality with dummy data."""
    print("\nTesting AlignmentEngine...")
    
    try:
        from subshift.align import AlignmentEngine
        from subshift.audio import AudioSample
        
        # Create alignment engine
        engine = AlignmentEngine(
            similarity_threshold=0.7,
            search_window=20,
            min_chars=40
        )
        print(f"✓ AlignmentEngine created: {type(engine)}")
        print(f"✓ Similarity threshold: {engine.similarity_threshold}")
        print(f"✓ Search window: {engine.search_window} minutes")
        
        # Create mock audio samples with dummy transcriptions
        mock_samples = [
            AudioSample(0, 300, Path("dummy1.wav")),  # 5 minutes
            AudioSample(1, 600, Path("dummy2.wav")),  # 10 minutes
        ]
        
        # Add mock transcriptions (from Matrix dialogue)
        mock_samples[0].transcription = "Is everything in place? You're not to relieve me. I know, but I felt like taking a shift."
        mock_samples[1].transcription = "You like him, don't you? You like watching him. Don't be ridiculous. We're going to kill him."
        
        print(f"✓ Created {len(mock_samples)} mock audio samples with transcriptions")
        
        return engine, mock_samples
        
    except Exception as e:
        print(f"✗ AlignmentEngine test failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def test_alignment_matching(engine, mock_samples, subtitle_processor):
    """Test the alignment matching process."""
    print("\nTesting alignment matching...")
    
    try:
        if not engine or not mock_samples or not subtitle_processor:
            print("✗ Missing components for alignment test")
            return False
        
        # Perform alignment
        matches = engine.align_samples(mock_samples, subtitle_processor)
        print(f"✓ Generated {len(matches)} alignment matches")
        
        # Display matches
        if matches:
            engine.display_matches(matches, debug=True)
        
        # Get successful matches
        successful = engine.get_successful_matches(matches)
        print(f"✓ Found {len(successful)} successful matches")
        
        return len(successful) > 0
        
    except Exception as e:
        print(f"✗ Alignment matching test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_offset_calculator():
    """Test OffsetCalculator functionality."""
    print("\nTesting OffsetCalculator...")
    
    try:
        from subshift.offset import OffsetCalculator
        from subshift.align import AlignmentMatch
        from subshift.audio import AudioSample
        
        # Create offset calculator
        calculator = OffsetCalculator()
        print(f"✓ OffsetCalculator created: {type(calculator)}")
        
        # Create mock alignment matches
        mock_sample = AudioSample(0, 300, Path("dummy.wav"))  # 5 minutes
        
        # Create a mock match indicating subtitles are 5 seconds ahead
        # (which should result in -5 second offset to correct)
        mock_match = AlignmentMatch(
            audio_sample_index=0,
            audio_sample_timestamp=300.0,  # 5 minutes
            audio_text="Is everything in place?",
            subtitle_minute=5,  # Found at minute 5
            subtitle_timestamp=305.0,  # 5 seconds ahead
            subtitle_text="Is everything in place?", 
            levenshtein_distance=0,
            similarity_score=0.85,
            is_match=True
        )
        
        mock_matches = [mock_match]
        
        # Calculate offsets
        offsets = calculator.calculate_sample_offsets(mock_matches)
        print(f"✓ Calculated {len(offsets)} offsets")
        
        if offsets:
            calculator.display_offset_summary()
        
        return len(offsets) > 0
        
    except Exception as e:
        print(f"✗ OffsetCalculator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("SubShift Component Testing")
    print("=" * 26)
    
    success_count = 0
    total_tests = 4
    
    # Test 1: SubtitleProcessor
    subtitle_processor, subtitle_count = test_subtitle_processor()
    if subtitle_processor and subtitle_count > 0:
        success_count += 1
        print("✅ SubtitleProcessor test passed!")
    else:
        print("❌ SubtitleProcessor test failed!")
    
    # Test 2: AlignmentEngine creation
    alignment_engine, mock_samples = test_alignment_engine()
    if alignment_engine and mock_samples:
        success_count += 1
        print("✅ AlignmentEngine test passed!")
    else:
        print("❌ AlignmentEngine test failed!")
    
    # Test 3: Alignment matching (only if previous tests passed)
    if alignment_engine and mock_samples and subtitle_processor:
        alignment_success = test_alignment_matching(alignment_engine, mock_samples, subtitle_processor)
        if alignment_success:
            success_count += 1
            print("✅ Alignment matching test passed!")
        else:
            print("❌ Alignment matching test failed!")
    else:
        print("❌ Skipping alignment matching test due to prerequisites")
    
    # Test 4: OffsetCalculator
    offset_success = test_offset_calculator()
    if offset_success:
        success_count += 1
        print("✅ OffsetCalculator test passed!")
    else:
        print("❌ OffsetCalculator test failed!")
    
    # Summary
    print(f"\n📊 Test Results: {success_count}/{total_tests} passed")
    
    if success_count == total_tests:
        print("🎉 All component tests passed! SubShift is fully functional.")
        return True
    else:
        print("⚠️  Some component tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
