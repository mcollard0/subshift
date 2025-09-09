#!/usr/bin/env python3
"""
Script to modify SRT subtitle timestamps by adding a fixed offset.

Usage: python3 modify_timestamps.py input.srt output.srt [offset_seconds]
"""
import sys
import re
from pathlib import Path


def parse_timestamp( timestamp_str ):
    """
    Parse SRT timestamp string into hours, minutes, seconds, milliseconds.
    
    Args:
        timestamp_str: String like "00:01:23,456"
        
    Returns:
        Tuple of (hours, minutes, seconds, milliseconds)
    """
    pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})';
    match = re.match( pattern, timestamp_str );
    if not match:
        raise ValueError( f"Invalid timestamp format: {timestamp_str}" );
    
    hours = int( match.group( 1 ) );
    minutes = int( match.group( 2 ) );
    seconds = int( match.group( 3 ) );
    milliseconds = int( match.group( 4 ) );
    
    return ( hours, minutes, seconds, milliseconds );


def format_timestamp( hours, minutes, seconds, milliseconds ):
    """
    Format time components back into SRT timestamp string.
    
    Args:
        hours, minutes, seconds, milliseconds: Integer time components
        
    Returns:
        Formatted timestamp string like "00:01:23,456"
    """
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}";


def add_seconds_to_timestamp( timestamp_str, offset_seconds ):
    """
    Add seconds to a timestamp with proper wraparound handling.
    
    Args:
        timestamp_str: Original timestamp string
        offset_seconds: Number of seconds to add
        
    Returns:
        New timestamp string with offset applied
    """
    hours, minutes, seconds, milliseconds = parse_timestamp( timestamp_str );
    
    # Convert everything to milliseconds for easier math
    total_ms = ( hours * 3600 + minutes * 60 + seconds ) * 1000 + milliseconds;
    offset_ms = offset_seconds * 1000;
    
    # Add offset
    new_total_ms = total_ms + offset_ms;
    
    # Convert back to components
    new_milliseconds = new_total_ms % 1000;
    total_seconds = new_total_ms // 1000;
    
    new_seconds = total_seconds % 60;
    total_minutes = total_seconds // 60;
    
    new_minutes = total_minutes % 60;
    new_hours = total_minutes // 60;
    
    # SRT format typically doesn't go beyond 24 hours, but we'll allow it
    if new_hours > 99:
        print( f"Warning: Hours exceed 99 in timestamp: {new_hours}" );
    
    return format_timestamp( new_hours, new_minutes, new_seconds, new_milliseconds );


def modify_srt_file( input_file, output_file, offset_seconds ):
    """
    Modify all timestamps in an SRT file by adding an offset.
    
    Args:
        input_file: Path to input SRT file
        output_file: Path to output SRT file
        offset_seconds: Seconds to add to each timestamp
    """
    print( f"Modifying '{input_file}' by adding {offset_seconds} seconds..." );
    
    timestamp_pattern = r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})';
    modified_lines = 0;
    
    with open( input_file, 'r', encoding='utf-8' ) as infile:
        lines = infile.readlines();
    
    with open( output_file, 'w', encoding='utf-8' ) as outfile:
        for line in lines:
            # Check if line contains timestamp
            match = re.search( timestamp_pattern, line );
            if match:
                start_time = match.group( 1 );
                end_time = match.group( 2 );
                
                # Modify timestamps
                new_start = add_seconds_to_timestamp( start_time, offset_seconds );
                new_end = add_seconds_to_timestamp( end_time, offset_seconds );
                
                # Replace in line
                new_line = line.replace( f"{start_time} --> {end_time}", f"{new_start} --> {new_end}" );
                outfile.write( new_line );
                modified_lines += 1;
                
                if modified_lines <= 5:  # Show first few modifications
                    print( f"  {start_time} --> {end_time}  =>  {new_start} --> {new_end}" );
            else:
                outfile.write( line );
    
    print( f"Modified {modified_lines} timestamp lines" );
    print( f"Output saved to: {output_file}" );


def main():
    """Main function to handle command line arguments and execute modification."""
    if len( sys.argv ) < 3:
        print( "Usage: python3 modify_timestamps.py input.srt output.srt [offset_seconds]" );
        print( "Default offset is 5 seconds if not specified" );
        sys.exit( 1 );
    
    input_file = Path( sys.argv[1] );
    output_file = Path( sys.argv[2] );
    offset_seconds = int( sys.argv[3] ) if len( sys.argv ) > 3 else 5;
    
    if not input_file.exists():
        print( f"Error: Input file '{input_file}' not found" );
        sys.exit( 1 );
    
    try:
        modify_srt_file( input_file, output_file, offset_seconds );
        print( f"✓ Successfully modified subtitle file with {offset_seconds}s offset" );
        
    except Exception as e:
        print( f"Error modifying file: {e}" );
        sys.exit( 1 );


if __name__ == "__main__":
    main();
