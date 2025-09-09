#!/usr/bin/env python3
"""
Test AudioProcessor functionality to verify FFmpeg integration is working.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_audio_processor_creation():
    """Test AudioProcessor can be created without errors."""
    print("Testing AudioProcessor creation...")
    
    try:
        from subshift.audio import AudioProcessor
        
        # Test basic creation
        processor = AudioProcessor(debug=True)
        print(f"✓ AudioProcessor created: {type(processor)}")
        print(f"✓ Sample rate: {processor.sample_rate}")
        print(f"✓ Channels: {processor.channels}")
        print(f"✓ Sample duration: {processor.sample_duration}s")
        
        return processor
        
    except Exception as e:
        print(f"✗ AudioProcessor creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_video_duration_detection(processor):
    """Test video duration detection with Matrix video file."""
    print("\nTesting video duration detection...")
    
    video_file = Path("/media/michael/FASTESTARCHIVE/Archive/Media/The Matrix (1999)/The.Matrix.1999.720p.BrRip.264.YIFY.mp4")
    
    if not video_file.exists():
        print(f"✗ Video file not found: {video_file}")
        return False
    
    try:
        duration = processor.get_video_duration(video_file)
        
        if duration is not None:
            print(f"✓ Video duration detected: {duration:.2f} seconds ({duration/60:.1f} minutes)")
            return duration
        else:
            print("⚠ Video duration detection returned None, testing fallback...")
            duration = processor.estimate_duration_from_filename(video_file)
            print(f"✓ Estimated duration: {duration:.2f} seconds ({duration/60:.1f} minutes)")
            return duration
            
    except Exception as e:
        print(f"✗ Video duration detection failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_sample_time_generation(processor, duration):
    """Test sample time generation."""
    print("\nTesting sample time generation...")
    
    try:
        sample_times = processor.generate_sample_times(duration, num_samples=4)
        print(f"✓ Generated {len(sample_times)} sample times")
        print(f"✓ Sample times (minutes): {[t/60 for t in sample_times[:5]]}")  # Show first 5
        
        return sample_times
        
    except Exception as e:
        print(f"✗ Sample time generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_single_audio_extraction(processor):
    """Test extracting a single short audio sample."""
    print("\nTesting single audio sample extraction...")
    
    video_file = Path("/media/michael/FASTESTARCHIVE/Archive/Media/The Matrix (1999)/The.Matrix.1999.720p.BrRip.264.YIFY.mp4")
    
    try:
        # Extract just 10 seconds from 5 minutes in for quick test
        sample = processor.extract_audio_sample(video_file, start_time=300, index=0)
        
        if sample:
            print(f"✓ Audio sample extracted: {sample}")
            print(f"✓ Sample file exists: {sample.file_path.exists()}")
            if sample.file_path.exists():
                file_size = sample.file_path.stat().st_size
                print(f"✓ Sample file size: {file_size} bytes ({file_size/1024:.1f} KB)")
                
                # Clean up test file
                sample.file_path.unlink()
                print("✓ Test file cleaned up")
            
            return True
        else:
            print("✗ Audio sample extraction returned None")
            return False
            
    except Exception as e:
        print(f"✗ Audio sample extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("SubShift AudioProcessor Testing")
    print("=" * 31)
    
    # Test 1: Create AudioProcessor
    processor = test_audio_processor_creation()
    if not processor:
        print("\n❌ AudioProcessor creation failed!")
        return False
    
    # Test 2: Video duration detection
    duration = test_video_duration_detection(processor)
    if not duration:
        print("\n❌ Video duration detection failed!")
        return False
    
    # Test 3: Sample time generation
    sample_times = test_sample_time_generation(processor, duration)
    if not sample_times:
        print("\n❌ Sample time generation failed!")
        return False
    
    # Test 4: Single audio extraction (most likely to fail)
    extraction_success = test_single_audio_extraction(processor)
    if not extraction_success:
        print("\n❌ Audio extraction failed!")
        return False
    
    print("\n✅ All AudioProcessor tests passed!")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
