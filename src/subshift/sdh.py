"""
SDH (Sound Description for Hearing Impaired) removal using AI analysis.

Cost Analysis for 100KB subtitle file:
- Typical SRT file: ~2000 lines, ~50 characters per line
- After cleaning/grouping: ~500 text chunks for analysis
- OpenAI GPT-4 Mini cost: ~$0.0002 per 1K tokens
- Estimated tokens: 500 chunks × 20 tokens = 10K tokens  
- Cost estimate: ~$0.002 (less than 1 cent) per 100KB subtitle file
"""
import re
from pathlib import Path
from typing import List, Tuple, Optional
import json

from .transcribe import create_transcription_engine
from .logging import get_logger


class SDHRemover:
    """
    AI-powered SDH (Sound Description) removal from subtitle files.
    
    Detects and removes sound effects, music descriptions, and non-dialogue text
    while preserving actual spoken dialogue.
    """
    
    def __init__( self, api_engine: str = "openai", api_key: str = "" ):
        self.logger = get_logger();
        self.api_engine = api_engine;
        self.api_key = api_key;
        
        # Common SDH patterns for quick filtering
        self.sdh_patterns = [
            r'\[.*?\]',           # [music playing]
            r'\(.*?\)',           # (door slam)  
            r'♪.*?♪',             # ♪ music lyrics ♪
            r'\*.*?\*',           # *sound effect*
            r'<.*?>',             # <applause>
            r'^[A-Z\s]+:',        # SPEAKER NAME:
            r'\b(MUSIC|SOUND|SFX|EFFECT)S?\b',  # Keywords
        ];
    
    def estimate_cost( self, subtitle_file: Path ) -> dict:
        """
        Estimate API cost for SDH removal on a subtitle file.
        
        Returns:
            Dictionary with cost estimates and file statistics
        """
        if not subtitle_file.exists():
            return { 'error': 'File not found' };
        
        file_size_kb = subtitle_file.stat().st_size / 1024;
        
        # Read and count lines
        with open( subtitle_file, 'r', encoding='utf-8' ) as f:
            lines = f.readlines();
        
        # Estimate text chunks (after grouping similar lines)
        text_lines = [ line.strip() for line in lines if line.strip() and not line.strip().isdigit() and '-->' not in line ];
        estimated_chunks = max( 1, len( text_lines ) // 4 );  # Group every 4 lines
        
        # Estimate tokens (rough approximation)
        avg_tokens_per_chunk = 20;
        total_tokens = estimated_chunks * avg_tokens_per_chunk;
        
        # Cost estimates (based on current OpenAI pricing)
        cost_per_1k_tokens = 0.0002;  # GPT-4 Mini pricing
        estimated_cost = ( total_tokens / 1000 ) * cost_per_1k_tokens;
        
        return {
            'file_size_kb': round( file_size_kb, 1 ),
            'total_lines': len( lines ),
            'text_lines': len( text_lines ),
            'estimated_chunks': estimated_chunks,
            'estimated_tokens': total_tokens,
            'estimated_cost_usd': round( estimated_cost, 4 ),
            'cost_per_100kb': round( ( estimated_cost / file_size_kb ) * 100, 4 )
        };
    
    def quick_sdh_filter( self, text: str ) -> str:
        """
        Quick pattern-based SDH removal for obvious cases.
        
        Args:
            text: Input subtitle text
            
        Returns:
            Text with obvious SDH patterns removed
        """
        original_text = text;
        
        for pattern in self.sdh_patterns:
            text = re.sub( pattern, '', text, flags=re.IGNORECASE );
        
        # Clean up extra whitespace
        text = re.sub( r'\s+', ' ', text ).strip();
        
        return text;
    
    def ai_sdh_analysis( self, text_chunks: List[str] ) -> List[bool]:
        """
        Use AI to analyze text chunks and identify SDH content.
        
        Args:
            text_chunks: List of subtitle text chunks to analyze
            
        Returns:
            List of booleans indicating whether each chunk is SDH (True) or dialogue (False)
        """
        if not text_chunks:
            return [];
        
        try:
            # Create AI engine for analysis
            if self.api_engine == "openai":
                import openai;
                client = openai.OpenAI( api_key=self.api_key );
                
                # Prepare prompt
                chunks_text = "\\n".join( f"{i+1}. {chunk}" for i, chunk in enumerate( text_chunks ) );
                
                prompt = f"""Analyze these subtitle text chunks and identify which ones are Sound Descriptions for Hearing Impaired (SDH) versus actual spoken dialogue.

SDH includes:
- Sound effects: [music], (door slam), *explosion*
- Music descriptions: ♪ song lyrics ♪  
- Non-dialogue sounds: <applause>, [phone ringing]
- Speaker labels: JOHN:, NARRATOR:

Dialogue includes:
- Actual spoken words by characters
- Conversation and speech content

Text chunks to analyze:
{chunks_text}

Respond with ONLY a JSON array of boolean values (true=SDH, false=dialogue) in the same order. Example: [true, false, true, false]""";

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[ { "role": "user", "content": prompt } ],
                    max_tokens=200,
                    temperature=0.1
                );
                
                result_text = response.choices[0].message.content.strip();
                
                # Parse JSON response
                try:
                    sdh_flags = json.loads( result_text );
                    if len( sdh_flags ) == len( text_chunks ):
                        return sdh_flags;
                    else:
                        self.logger.warning( f"AI response length mismatch: {len( sdh_flags )} vs {len( text_chunks )}" );
                except json.JSONDecodeError:
                    self.logger.warning( f"Failed to parse AI JSON response: {result_text}" );
                    
            else:
                self.logger.warning( f"AI SDH analysis not implemented for {self.api_engine}" );
                
        except Exception as e:
            self.logger.error( f"AI SDH analysis failed: {e}" );
        
        # Fallback: use pattern-based detection
        return [ self.is_likely_sdh( chunk ) for chunk in text_chunks ];
    
    def is_likely_sdh( self, text: str ) -> bool:
        """
        Pattern-based heuristic to detect likely SDH content.
        
        Args:
            text: Text chunk to analyze
            
        Returns:
            True if text is likely SDH, False if likely dialogue
        """
        if not text or len( text.strip() ) < 3:
            return True;  # Too short, likely not dialogue
        
        # Check for obvious SDH patterns
        for pattern in self.sdh_patterns:
            if re.search( pattern, text, re.IGNORECASE ):
                return True;
        
        # Check for music-related keywords
        music_keywords = [ 'music', 'song', 'melody', 'tune', 'playing', 'singing' ];
        if any( keyword in text.lower() for keyword in music_keywords ):
            return True;
        
        # Check for sound effect keywords
        sound_keywords = [ 'sound', 'noise', 'effect', 'audio', 'sfx' ];
        if any( keyword in text.lower() for keyword in sound_keywords ):
            return True;
        
        # If it looks like normal dialogue, keep it
        return False;
    
    def remove_sdh_from_file( self, subtitle_file: Path, output_file: Optional[Path] = None, use_ai: bool = True ) -> Path:
        """
        Remove SDH content from subtitle file.
        
        Args:
            subtitle_file: Input SRT file
            output_file: Output file path (default: original + .no-sdh.srt)
            use_ai: Whether to use AI analysis (default: True)
            
        Returns:
            Path to cleaned subtitle file
        """
        if not subtitle_file.exists():
            raise FileNotFoundError( f"Subtitle file not found: {subtitle_file}" );
        
        if output_file is None:
            output_file = subtitle_file.parent / f"{subtitle_file.stem}.no-sdh{subtitle_file.suffix}";
        
        self.logger.info( f"Removing SDH from {subtitle_file}" );
        
        # Read subtitle file
        with open( subtitle_file, 'r', encoding='utf-8' ) as f:
            lines = f.readlines();
        
        # Parse SRT structure
        cleaned_lines = [];
        current_subtitle = [];
        subtitle_count = 0;
        
        i = 0;
        while i < len( lines ):
            line = lines[i].strip();
            
            if line.isdigit():  # Subtitle index
                # Process previous subtitle if exists
                if current_subtitle:
                    cleaned_subtitle = self._process_subtitle_block( current_subtitle, use_ai );
                    if cleaned_subtitle:
                        subtitle_count += 1;
                        cleaned_lines.extend( [ str( subtitle_count ), cleaned_subtitle[1], cleaned_subtitle[2] ] );
                        if len( cleaned_subtitle ) > 3:
                            cleaned_lines.extend( cleaned_subtitle[3:] );
                        cleaned_lines.append( "" );
                
                # Start new subtitle
                current_subtitle = [ line ];
                
            elif line:
                current_subtitle.append( line );
                
            i += 1;
        
        # Process final subtitle
        if current_subtitle:
            cleaned_subtitle = self._process_subtitle_block( current_subtitle, use_ai );
            if cleaned_subtitle:
                subtitle_count += 1;
                cleaned_lines.extend( [ str( subtitle_count ), cleaned_subtitle[1], cleaned_subtitle[2] ] );
                if len( cleaned_subtitle ) > 3:
                    cleaned_lines.extend( cleaned_subtitle[3:] );
        
        # Write cleaned file
        with open( output_file, 'w', encoding='utf-8' ) as f:
            for line in cleaned_lines:
                f.write( line + "\\n" );
        
        self.logger.info( f"SDH removal complete. Cleaned file saved to: {output_file}" );
        self.logger.info( f"Subtitles reduced from {len( [ l for l in lines if l.strip().isdigit() ] )} to {subtitle_count}" );
        
        return output_file;
    
    def _process_subtitle_block( self, subtitle_lines: List[str], use_ai: bool ) -> Optional[List[str]]:
        """
        Process a single subtitle block and determine if it should be kept.
        
        Args:
            subtitle_lines: Lines for one subtitle (index, timestamp, text...)
            use_ai: Whether to use AI analysis
            
        Returns:
            Processed subtitle lines or None if should be removed
        """
        if len( subtitle_lines ) < 3:
            return None;  # Invalid subtitle block
        
        index = subtitle_lines[0];
        timestamp = subtitle_lines[1];
        text_lines = subtitle_lines[2:];
        
        # Combine text lines
        full_text = " ".join( text_lines ).strip();
        
        if not full_text:
            return None;  # Empty subtitle
        
        # Quick pattern filter first
        cleaned_text = self.quick_sdh_filter( full_text );
        
        if not cleaned_text or len( cleaned_text ) < 3:
            return None;  # Removed by pattern filter
        
        # AI analysis for remaining text (if enabled and different from original)
        if use_ai and cleaned_text != full_text:
            is_sdh = self.ai_sdh_analysis( [ cleaned_text ] )[0];
            if is_sdh:
                return None;  # AI identified as SDH
        elif not use_ai:
            # Pattern-based analysis only
            if self.is_likely_sdh( cleaned_text ):
                return None;
        
        # Keep this subtitle
        return [ index, timestamp, cleaned_text ];
