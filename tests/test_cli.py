"""
Basic test cases for SubShift CLI functionality.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add src directory to path for testing
sys.path.insert( 0, str( Path( __file__ ).parent.parent / "src" ) );

from subshift.cli import SubShiftCLI


class TestSubShiftCLI:
    """Test cases for SubShift CLI interface."""
    
    def test_cli_initialization( self ):
        """Test CLI object creation."""
        cli = SubShiftCLI();
        assert cli.parser is not None;
        assert cli.args is None;
        assert cli.logger is None;
    
    def test_argument_parsing_missing_required( self ):
        """Test CLI with missing required arguments."""
        cli = SubShiftCLI();
        
        with pytest.raises( SystemExit ):
            cli.parse_args( [] );  # No arguments provided
    
    @patch( 'subshift.cli.Path.exists' )
    @patch( 'subshift.cli.os.getenv' )
    def test_argument_parsing_valid( self, mock_getenv, mock_exists ):
        """Test CLI with valid arguments."""
        # Mock file existence
        mock_exists.return_value = True;
        
        # Mock environment variables
        mock_getenv.side_effect = lambda key: {
            'OPENAI_API_KEY': 'test_openai_key',
            'GOOGLE_PLACES_API_KEY': 'test_google_key'
        }.get( key );
        
        cli = SubShiftCLI();
        args = cli.parse_args( [
            '--video', 'test.mp4',
            '--subs', 'test.srt',
            '--debug'
        ] );
        
        assert args.media == Path( 'test.mp4' );
        assert args.subtitle == Path( 'test.srt' );
        assert args.debug == True;
        assert args.api == 'openai';  # Default
    
    def test_similarity_threshold_validation( self ):
        """Test similarity threshold validation."""
        cli = SubShiftCLI();
        
        # Mock environment and file checks to focus on validation
        with patch( 'subshift.cli.Path.exists', return_value=True ), \
             patch( 'subshift.cli.os.getenv', return_value='test_key' ):
            
            with pytest.raises( SystemExit ):
                cli.parse_args( [
                    '--video', 'test.mp4',
                    '--subs', 'test.srt',  
                    '--similarity-threshold', '1.5'  # Invalid: > 1.0
                ] );
    
    @patch( 'subshift.cli.Path.exists' )
    def test_file_validation( self, mock_exists ):
        """Test file existence validation."""
        cli = SubShiftCLI();
        
        # Mock non-existent files
        mock_exists.return_value = False;
        
        with pytest.raises( SystemExit ):
            cli.parse_args( [
                '--video', 'nonexistent.mp4',
                '--subs', 'nonexistent.srt'
            ] );
    
    def test_api_key_retrieval( self ):
        """Test API key retrieval based on engine selection."""
        cli = SubShiftCLI();
        cli.openai_api_key = "test_openai_key";
        cli.google_api_key = "test_google_key";
        
        # Mock args for different engines
        cli.args = Mock();
        
        cli.args.api = "openai";
        assert cli.get_api_key() == "test_openai_key";
        
        cli.args.api = "google";
        assert cli.get_api_key() == "test_google_key";
        
        cli.args.api = "unknown";
        assert cli.get_api_key() is None;


class TestEnvironmentLoading:
    """Test environment variable loading."""
    
    @patch.dict( os.environ, {
        'OPENAI_API_KEY': 'env_openai_key',
        'GOOGLE_PLACES_API_KEY': 'env_google_key'
    } )
    def test_environment_variable_loading( self ):
        """Test loading API keys from environment variables."""
        cli = SubShiftCLI();
        cli._load_environment();
        
        assert cli.openai_api_key == 'env_openai_key';
        assert cli.google_api_key == 'env_google_key';
    
    @patch.dict( os.environ, {}, clear=True )
    def test_missing_environment_variables( self ):
        """Test handling of missing environment variables."""
        cli = SubShiftCLI();
        cli._load_environment();
        
        assert cli.openai_api_key is None;
        assert cli.google_api_key is None;


if __name__ == '__main__':
    pytest.main( [ __file__ ] );
