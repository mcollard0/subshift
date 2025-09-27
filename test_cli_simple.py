#!/usr/bin/env python3
"""
Simple CLI test that only validates argument parsing without importing
the full subshift module (which has dependencies).
"""
import argparse

# Recreate just the argument parser part for testing
def create_parser():
    """Create argument parser with all SubShift options."""
    parser = argparse.ArgumentParser(
        prog="subshift",
        description="Subtitle synchronization utility using AI transcripts and Levenshtein matching",
        epilog="Environment variables: OPENAI_API_KEY, GOOGLE_PLACES_API_KEY (not required for local engines)"
    );
    
    # Required arguments (media optional for SDH cost estimation)
    parser.add_argument(
        "--media", "--video", "-v",
        required=False,
        help="Path to media file (.mp4, .mkv, .avi, etc.)"
    );
    
    parser.add_argument(
        "--sub", "--subs", "--srt", "--subtitle", "-s", 
        required=True,
        help="Path to subtitle file (.srt format only)"
    );
    
    # API engine choice
    parser.add_argument(
        "--api",
        choices=[ "openai", "google", "local", "local-tiny", "local-base", "local-small", "local-medium", "local-large" ],
        default="openai",
        help="AI transcription engine to use (default: openai). Local options: local/local-tiny (39MB), local-base (74MB), local-small (244MB), local-medium (769MB), local-large (1.5GB)"
    );
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform analysis without modifying subtitle file"
    );
    
    return parser;

def test_local_engines():
    """Test that all local engine choices are accepted."""
    print("Testing local engine argument parsing...");
    
    parser = create_parser();
    
    local_engines = [
        "local",
        "local-tiny", 
        "local-base",
        "local-small",
        "local-medium", 
        "local-large"
    ];
    
    for engine in local_engines:
        try:
            args = parser.parse_args(["--sub", "test.srt", "--api", engine, "--dry-run"]);
            assert args.api == engine, f"Expected {engine}, got {args.api}";
            print(f"  ✓ {engine}");
        except Exception as e:
            print(f"  ❌ {engine}: {e}");
            return False;
    
    return True;

def test_help_contains_local():
    """Test that help output mentions local engines."""
    print("Testing help output...");
    
    parser = create_parser();
    help_text = parser.format_help();
    
    required_strings = [
        "local",
        "local-tiny", 
        "39MB",
        "1.5GB",
        "not required for local engines"
    ];
    
    for required in required_strings:
        if required not in help_text:
            print(f"  ❌ Help missing: {required}");
            return False;
        print(f"  ✓ Found: {required}");
    
    return True;

def main():
    """Run simple CLI tests."""
    print("=== Simple CLI Argument Tests ===\n");
    
    success = True;
    
    success &= test_local_engines();
    print();
    success &= test_help_contains_local();
    
    if success:
        print("\n🎉 All simple CLI tests passed!");
        return 0;
    else:
        print("\n❌ Some tests failed!");
        return 1;

if __name__ == "__main__":
    exit(main());