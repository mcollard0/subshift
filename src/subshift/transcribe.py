"""
Transcription engines for converting audio to text using AI APIs.
"""
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import openai
import whisper
from google.cloud import speech

from .audio import AudioSample
from .logging import get_logger


class TranscriptionEngine( ABC ):
    """Abstract base class for AI transcription engines."""
    
    def __init__( self, api_key: Optional[str] = None ):
        self.api_key = api_key;
        self.logger = get_logger();
    
    @abstractmethod
    def transcribe( self, audio_sample: AudioSample ) -> str:
        """Transcribe audio sample to text."""
        pass
    
    def clean_transcript( self, text: str ) -> str:
        """
        Clean transcript text by removing HTML, WebVTT styling, and formatting.
        
        Removes:
        - HTML tags (<b>, <i>, etc.)
        - WebVTT styling (color:, font:, etc.)
        - Bracketed descriptions [music], (laughter)
        - Extra whitespace and newlines
        """
        if not text:
            return "";
        
        # Remove HTML tags
        text = re.sub( r'<[^>]+>', '', text );
        
        # Remove WebVTT color/styling tags
        text = re.sub( r'<c\.[^>]+>', '', text );
        text = re.sub( r'</c>', '', text );
        
        # Remove bracketed sound descriptions and speaker labels
        text = re.sub( r'\[([^\]]+)\]', '', text );  # [music], [sound effect]
        text = re.sub( r'\(([^)]+)\)', '', text );   # (laughter), (applause)
        
        # Remove common subtitle artifacts
        text = re.sub( r'♪[^♪]*♪', '', text );  # Music notes
        text = re.sub( r'[♪♫★►▼]', '', text );  # Various symbols
        
        # Clean up whitespace
        text = re.sub( r'\s+', ' ', text );  # Multiple spaces to single
        text = re.sub( r'\n+', ' ', text );  # Newlines to spaces
        text = text.strip();
        
        return text;
    
    def retry_with_backoff( self, func, max_retries: int = 3 ):
        """Execute function with exponential backoff retry."""
        for attempt in range( max_retries ):
            try:
                return func();
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e;
                
                wait_time = 2 ** attempt;
                self.logger.warning( f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}" );
                time.sleep( wait_time );


class WhisperEngine( TranscriptionEngine ):
    """OpenAI Whisper transcription engine (primary, default)."""
    
    def __init__( self, api_key: str ):
        super().__init__( api_key );
        self.client = openai.OpenAI( api_key=api_key );
        self.model = "whisper-1";
    
    def transcribe( self, audio_sample: AudioSample ) -> str:
        """
        Transcribe audio sample using OpenAI Whisper API.
        
        Args:
            audio_sample: AudioSample object with file path
            
        Returns:
            Cleaned transcript text
        """
        self.logger.debug( f"Transcribing {audio_sample} with Whisper" );
        
        def _transcribe():
            with open( audio_sample.file_path, "rb" ) as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text",
                    prompt="Return only the spoken words without any formatting, timestamps, or descriptions."
                );
                return response;
        
        try:
            transcript = self.retry_with_backoff( _transcribe );
            cleaned_text = self.clean_transcript( transcript );
            
            self.logger.debug( f"Whisper transcript: {cleaned_text[:100]}..." );
            return cleaned_text;
            
        except Exception as e:
            self.logger.error( f"Whisper transcription failed for {audio_sample}: {e}" );
            return "";


class GoogleSpeechEngine( TranscriptionEngine ):
    """Google Cloud Speech-to-Text transcription engine (secondary)."""
    
    def __init__( self, api_key: str ):
        super().__init__( api_key );
        
        # Note: Google Cloud Speech-to-Text typically uses service account JSON,
        # but user specifically requested GOOGLE_PLACES_API_KEY usage
        import os;
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = api_key;
        
        self.client = speech.SpeechClient();
        
        # Audio configuration
        self.config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            enable_word_confidence=True,
            model="latest_long"
        );
    
    def transcribe( self, audio_sample: AudioSample ) -> str:
        """
        Transcribe audio sample using Google Speech-to-Text API.
        
        Args:
            audio_sample: AudioSample object with file path
            
        Returns:
            Cleaned transcript text
        """
        self.logger.debug( f"Transcribing {audio_sample} with Google Speech" );
        
        def _transcribe():
            # Read audio file
            with open( audio_sample.file_path, "rb" ) as audio_file:
                content = audio_file.read();
            
            audio = speech.RecognitionAudio( content=content );
            
            # Perform transcription
            response = self.client.recognize( 
                config=self.config, 
                audio=audio 
            );
            
            # Extract transcript from response
            transcript_parts = [];
            for result in response.results:
                if result.alternatives:
                    transcript_parts.append( result.alternatives[0].transcript );
            
            return " ".join( transcript_parts );
        
        try:
            transcript = self.retry_with_backoff( _transcribe );
            cleaned_text = self.clean_transcript( transcript );
            
            self.logger.debug( f"Google Speech transcript: {cleaned_text[:100]}..." );
            return cleaned_text;
            
        except Exception as e:
            self.logger.error( f"Google Speech transcription failed for {audio_sample}: {e}" );
            return "";


def create_transcription_engine( api_name: str, api_key: str ) -> TranscriptionEngine:
    """
    Factory function to create appropriate transcription engine.
    
    Args:
        api_name: "openai" or "google"
        api_key: API key for the service
        
    Returns:
        Initialized transcription engine
    """
    if api_name == "openai":
        return WhisperEngine( api_key );
    elif api_name == "google":
        return GoogleSpeechEngine( api_key );
    else:
        raise ValueError( f"Unknown transcription engine: {api_name}" );
