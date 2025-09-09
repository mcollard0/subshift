#!/usr/bin/env python3
"""
Debug script to test ffmpeg-python functionality with the Matrix video.
"""
import ffmpeg
import sys
from pathlib import Path

def test_ffmpeg_probe( video_file ):
    """Test ffmpeg.probe functionality."""
    print( f"Testing ffmpeg.probe on: {video_file}" );
    
    try:
        probe = ffmpeg.probe( str( video_file ) );
        print( f"Probe type: {type( probe )}" );
        print( f"Probe keys: {probe.keys() if hasattr( probe, 'keys' ) else 'No keys method'}" );
        
        if 'format' in probe:
            format_info = probe['format'];
            print( f"Format info: {format_info}" );
            if 'duration' in format_info:
                duration = float( format_info['duration'] );
                print( f"Duration: {duration} seconds ({duration/60:.1f} minutes)" );
            else:
                print( "No duration field in format" );
        else:
            print( "No format field in probe result" );
            
    except Exception as e:
        print( f"ffmpeg.probe failed: {e}" );
        import traceback;
        traceback.print_exc();

def test_ffmpeg_extraction( video_file ):
    """Test basic ffmpeg audio extraction."""
    print( f"\nTesting ffmpeg extraction on: {video_file}" );
    
    try:
        output_file = "test_sample.wav";
        start_time = 300;  # 5 minutes
        duration = 10;     # 10 seconds for quick test
        
        stream = ffmpeg.input( str( video_file ), ss=start_time, t=duration );
        print( f"Input stream type: {type( stream )}" );
        
        stream = ffmpeg.output(
            stream,
            output_file,
            acodec='pcm_s16le',
            ar=16000,
            ac=1,
            f='wav'
        );
        print( f"Output stream type: {type( stream )}" );
        
        # Test run
        print( "Attempting to run ffmpeg..." );
        ffmpeg.run( stream, overwrite_output=True, quiet=True );
        
        # Check result
        output_path = Path( output_file );
        if output_path.exists():
            file_size = output_path.stat().st_size;
            print( f"✓ Successfully extracted audio: {output_file} ({file_size} bytes)" );
            output_path.unlink();  # Clean up
        else:
            print( "✗ Audio extraction failed - no output file" );
            
    except Exception as e:
        print( f"ffmpeg extraction failed: {e}" );
        import traceback;
        traceback.print_exc();

def main():
    video_file = Path( "/media/michael/FASTESTARCHIVE/Archive/Media/The Matrix (1999)/The.Matrix.1999.720p.BrRip.264.YIFY.mp4" );
    
    if not video_file.exists():
        print( f"Video file not found: {video_file}" );
        sys.exit( 1 );
    
    print( f"Testing ffmpeg-python with video: {video_file.name}" );
    print( f"File size: {video_file.stat().st_size / (1024*1024):.1f} MB" );
    
    test_ffmpeg_probe( video_file );
    test_ffmpeg_extraction( video_file );

if __name__ == "__main__":
    main();
