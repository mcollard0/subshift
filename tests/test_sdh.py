"""
Test cases for SDH (Sound Description for Hearing Impaired) removal functionality.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add src directory to path for testing
sys.path.insert( 0, str( Path( __file__ ).parent.parent / "src" ) );

from subshift.sdh import SDHRemover


class TestSDHRemover:
    """Test cases for SDH removal functionality."""
    
    def test_sdh_remover_initialization( self ):
        """Test SDH remover object creation."""
        remover = SDHRemover();
        assert remover.api_engine == "openai";
        assert remover.api_key == "";
        assert len( remover.sdh_patterns ) > 0;
    
    def test_quick_sdh_filter( self ):
        """Test pattern-based SDH filtering."""
        remover = SDHRemover();
        
        # Test obvious SDH patterns
        test_cases = [
            ( "[music playing]", "" ),
            ( "(door slam)", "" ),
            ( "♪ theme song ♪", "" ),
            ( "*explosion*", "" ),
            ( "<applause>", "" ),
            ( "NARRATOR: Once upon a time", "" ),
            ( "Hello, how are you?", "Hello, how are you?" ),  # Normal dialogue
            ( "I'm fine, thanks [music] for asking", "I'm fine, thanks  for asking" )
        ];
        
        for input_text, expected in test_cases:
            result = remover.quick_sdh_filter( input_text );
            assert result.strip() == expected.strip();
    
    def test_is_likely_sdh( self ):
        """Test heuristic SDH detection."""
        remover = SDHRemover();
        
        # Should be identified as SDH
        sdh_examples = [
            "[door creaks]",
            "(music playing)",
            "background music continues",
            "sound of rain",
            "sfx: explosion",
            "",  # Empty text
            "a"   # Too short
        ];
        
        for text in sdh_examples:
            assert remover.is_likely_sdh( text ) == True, f"Should be SDH: '{text}'";
        
        # Should be identified as dialogue
        dialogue_examples = [
            "Hello, how are you today?",
            "I think we should go now.",
            "What time is the meeting?",
            "That's a great idea!"
        ];
        
        for text in dialogue_examples:
            assert remover.is_likely_sdh( text ) == False, f"Should be dialogue: '{text}'";
    
    @patch( 'builtins.open' )
    def test_cost_estimation( self, mock_open ):
        """Test cost estimation for SDH removal."""
        # Mock file content
        mock_file_content = """1
00:00:01,000 --> 00:00:03,000
Hello there!

2
00:00:04,000 --> 00:00:06,000
[music playing]

3
00:00:07,000 --> 00:00:09,000
How are you doing?
""";
        
        mock_open.return_value.__enter__.return_value.readlines.return_value = mock_file_content.split( '\\n' );
        
        remover = SDHRemover();
        
        # Mock file size
        mock_file = Mock();
        mock_file.exists.return_value = True;
        mock_file.stat.return_value.st_size = 1024;  # 1KB
        
        with patch( 'pathlib.Path.exists', return_value=True ), \
             patch( 'pathlib.Path.stat' ) as mock_stat:
            
            mock_stat.return_value.st_size = 1024;
            
            result = remover.estimate_cost( mock_file );
            
            assert 'file_size_kb' in result;
            assert 'estimated_cost_usd' in result;
            assert 'cost_per_100kb' in result;
            assert result['file_size_kb'] == 1.0;
            assert result['estimated_cost_usd'] >= 0;
    
    def test_cost_estimation_missing_file( self ):
        """Test cost estimation with missing file."""
        remover = SDHRemover();
        
        with patch( 'pathlib.Path.exists', return_value=False ):
            result = remover.estimate_cost( Path( "nonexistent.srt" ) );
            assert result == { 'error': 'File not found' };


class TestSDHPatterns:
    """Test SDH pattern recognition."""
    
    def test_music_patterns( self ):
        """Test music-related SDH patterns."""
        remover = SDHRemover();
        
        music_patterns = [
            "♪ Happy birthday to you ♪",
            "[upbeat music]",
            "(classical music playing)",
            "*jazz music*",
            "background song continues"
        ];
        
        for pattern in music_patterns:
            assert remover.is_likely_sdh( pattern ), f"Should detect music SDH: '{pattern}'";
    
    def test_sound_effect_patterns( self ):
        """Test sound effect SDH patterns."""
        remover = SDHRemover();
        
        sound_patterns = [
            "[door slams]",
            "(phone ringing)",
            "*car engine roars*",
            "<crowd cheering>",
            "footsteps approaching"
        ];
        
        for pattern in sound_patterns:
            assert remover.is_likely_sdh( pattern ), f"Should detect sound effect SDH: '{pattern}'";
    
    def test_speaker_labels( self ):
        """Test speaker label detection."""
        remover = SDHRemover();
        
        speaker_labels = [
            "NARRATOR: The story begins...",
            "JOHN: Hello there!",
            "VOICE OVER: Meanwhile..."
        ];
        
        for label in speaker_labels:
            cleaned = remover.quick_sdh_filter( label );
            # Should remove the speaker label part
            assert ":" not in cleaned or len( cleaned ) < len( label );


if __name__ == '__main__':
    pytest.main( [ __file__ ] );
