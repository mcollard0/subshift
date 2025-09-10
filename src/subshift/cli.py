"""
CLI entry point for SubShift with argument parsing and environment variable loading.
"""
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from .logging import setup_logging


class SubShiftCLI:
    """
    Command line interface for SubShift subtitle synchronization.
    
    Supports command line arguments with environment variable overrides
    for API keys and other secrets.
    """
    
    def __init__( self ):
        self.parser = self._create_parser();
        self.args = None;
        self.logger = None;
    
    def _create_parser( self ):
        """Create argument parser with all SubShift options."""
        parser = argparse.ArgumentParser(
            prog="subshift",
            description="Subtitle synchronization utility using AI transcripts and Levenshtein matching",
            epilog="Environment variables: OPENAI_API_KEY, GOOGLE_PLACES_API_KEY"
        );
        
        # Required arguments (media optional for SDH cost estimation)
        parser.add_argument(
            "--media", "--video", "-v",
            required=False,
            type=Path,
            dest="media",
            help="Path to media file (.mp4, .mkv, .avi, etc.)"
        );
        
        parser.add_argument(
            "--sub", "--subs", "--srt", "--subtitle", "-s", 
            required=True,
            type=Path,
            dest="subtitle",
            help="Path to subtitle file (.srt format only)"
        );
        
        # Optional parameters
        parser.add_argument(
            "--search-window",
            type=int,
            default=20,
            help="Search window in minutes for subtitle matching (default: 20)"
        );
        
        parser.add_argument(
            "--similarity-threshold",
            type=float,
            default=0.65,
            help="Similarity threshold for Levenshtein matching (0.0-1.0, default: 0.65)"
        );
        
        parser.add_argument(
            "--min-chars",
            type=int,
            default=40,
            help="Minimum characters required for subtitle matching (default: 40)"
        );
        
        parser.add_argument(
            "--samples",
            type=int,
            default=16,
            help="Number of audio samples to extract (default: 16, uses adaptive sampling)"
        );
        
        parser.add_argument(
            "--api",
            choices=[ "openai", "google" ],
            default="openai",
            help="AI transcription engine to use (default: openai)"
        );
        
        # Mode flags  
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Enable debug mode with verbose output"
        );
        
        parser.add_argument(
            "--curses",
            action="store_true", 
            help="Use curses UI for interactive progress display"
        );
        
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform analysis without modifying subtitle file"
        );
        
        parser.add_argument(
            "--remove-sdh",
            action="store_true",
            help="Remove SDH (Sound Description for Hearing Impaired) content from subtitles"
        );
        
        parser.add_argument(
            "--sdh-cost-estimate",
            action="store_true",
            help="Show cost estimate for SDH removal and exit"
        );
        
        return parser;
    
    def _load_environment( self ):
        """Load environment variables from .env file and system."""
        # Load from .env file if it exists
        env_file = Path( ".env" );
        if env_file.exists():
            load_dotenv( env_file );
        
        # Load API keys from environment
        self.openai_api_key = os.getenv( "OPENAI_API_KEY" );
        self.google_api_key = os.getenv( "GOOGLE_PLACES_API_KEY" );
    
    def _validate_arguments( self ):
        """Validate parsed arguments and environment setup."""
        errors = [];
        
        # Check if media file is required (not for SDH cost estimation)
        if not self.args.sdh_cost_estimate and not self.args.media:
            errors.append( "Media file is required except for SDH cost estimation" );
        
        # Check if files exist (when provided)
        if self.args.media and not self.args.media.exists():
            errors.append( f"Media file not found: {self.args.media}" );
        
        if not self.args.subtitle.exists():
            errors.append( f"Subtitle file not found: {self.args.subtitle}" );
        
        # Check subtitle file extension
        if self.args.subtitle.suffix.lower() != ".srt":
            errors.append( f"Only .srt subtitle files are supported, got: {self.args.subtitle.suffix}" );
        
        # Check API key availability
        if self.args.api == "openai" and not self.openai_api_key:
            errors.append( "OpenAI API key not found. Set OPENAI_API_KEY environment variable." );
        
        if self.args.api == "google" and not self.google_api_key:
            errors.append( "Google API key not found. Set GOOGLE_PLACES_API_KEY environment variable." );
        
        # Validate numeric parameters
        if not ( 0.0 <= self.args.similarity_threshold <= 1.0 ):
            errors.append( "Similarity threshold must be between 0.0 and 1.0" );
        
        if self.args.min_chars < 1:
            errors.append( "Minimum characters must be at least 1" );
        
        if self.args.samples < 1:
            errors.append( "Number of samples must be at least 1" );
        
        if self.args.search_window < 1:
            errors.append( "Search window must be at least 1 minute" );
        
        return errors;
    
    def parse_args( self, argv=None ):
        """Parse command line arguments and validate configuration."""
        self.args = self.parser.parse_args( argv );
        
        # Setup logging based on debug flag
        self.logger = setup_logging( debug=self.args.debug );
        
        # Load environment variables
        self._load_environment();
        
        # Validate everything
        errors = self._validate_arguments();
        if errors:
            self.logger.error( "Configuration errors:" );
            for error in errors:
                self.logger.error( f"  - {error}" );
            sys.exit( 1 );
        
        # Log startup information
        self.logger.info( f"SubShift v0.1.0 starting..." );
        if self.args.media:
            self.logger.info( f"Media: {self.args.media}" );
        self.logger.info( f"Subtitles: {self.args.subtitle}" );
        self.logger.info( f"AI Engine: {self.args.api}" );
        self.logger.info( f"Debug mode: {self.args.debug}" );
        
        return self.args;
    
    def get_api_key( self ):
        """Get the appropriate API key based on selected engine."""
        if self.args.api == "openai":
            return self.openai_api_key;
        elif self.args.api == "google":
            return self.google_api_key;
        return None;


def main():
    """Main entry point for the SubShift CLI."""
    cli = SubShiftCLI();
    args = cli.parse_args();
    
    # Handle SDH cost estimation
    if args.sdh_cost_estimate:
        from .sdh import SDHRemover;
        
        sdh_remover = SDHRemover( args.api, cli.get_api_key() );
        cost_info = sdh_remover.estimate_cost( args.subtitle );
        
        if 'error' in cost_info:
            cli.logger.error( f"Cost estimation failed: {cost_info['error']}" );
            sys.exit( 1 );
        
        cli.logger.info( "\n=== SDH REMOVAL COST ESTIMATE ===" );
        cli.logger.info( f"File: {args.subtitle}" );
        cli.logger.info( f"Size: {cost_info['file_size_kb']} KB" );
        cli.logger.info( f"Text lines: {cost_info['text_lines']}" );
        cli.logger.info( f"Estimated AI chunks: {cost_info['estimated_chunks']}" );
        cli.logger.info( f"Estimated tokens: {cost_info['estimated_tokens']:,}" );
        cli.logger.info( f"Estimated cost: ${cost_info['estimated_cost_usd']:.4f} USD" );
        cli.logger.info( f"Cost per 100KB: ${cost_info['cost_per_100kb']:.4f} USD" );
        cli.logger.info( "\nNote: This is an estimate based on OpenAI GPT-4 Mini pricing." );
        return;
    
    # Import and run the main synchronization process
    from .sync import SubtitleSynchronizer;
    
    synchronizer = SubtitleSynchronizer(
        video_file=args.media,
        subtitle_file=args.subtitle,
        api_engine=args.api,
        api_key=cli.get_api_key(),
        search_window=args.search_window,
        similarity_threshold=args.similarity_threshold,
        min_chars=args.min_chars,
        samples=args.samples,
        debug=args.debug,
        use_curses=args.curses,
        dry_run=args.dry_run,
        remove_sdh=args.remove_sdh
    );
    
    try:
        result = synchronizer.run();
        if result:
            cli.logger.info( "Subtitle synchronization completed successfully!" );
        else:
            cli.logger.error( "Subtitle synchronization failed!" );
            sys.exit( 1 );
    except KeyboardInterrupt:
        cli.logger.warning( "Interrupted by user" );
        sys.exit( 130 );
    except Exception as e:
        cli.logger.error( f"Unexpected error: {e}" );
        if args.debug:
            raise;
        sys.exit( 1 );


if __name__ == "__main__":
    main();
