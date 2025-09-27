"""
Transcription engines for converting audio to text using AI APIs and local models.
"""
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import openai
from google.cloud import speech

from .audio import AudioSample
from .logging import get_logger
from .hardware import get_system_capabilities, WhisperConfig


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
    
    def classify_error( self, error: Exception ) -> Tuple[bool, str]:
        """Classify error as transient or fatal.
        
        Returns:
            Tuple of (is_transient, error_category)
        """
        error_str = str( error ).lower();
        
        # Transient errors (retryable)
        transient_patterns = [
            'timeout', 'rate limit', 'quota', 'network', 'connection',
            'temporary', '429', '503', '502', '500', 'unavailable'
        ];
        
        if any( pattern in error_str for pattern in transient_patterns ):
            return True, "network/quota";
        
        # Fatal errors (not retryable)
        fatal_patterns = [
            'authentication', 'unauthorized', '401', '403', 'invalid api key',
            'file not found', 'unsupported format', 'invalid audio'
        ];
        
        if any( pattern in error_str for pattern in fatal_patterns ):
            return False, "authentication/format";
        
        # Default to transient for unknown errors
        return True, "unknown";
    
    def retry_with_backoff( self, func, max_retries: int = 3 ):
        """Execute function with exponential backoff retry and error classification."""
        last_error = None;
        
        for attempt in range( max_retries ):
            try:
                return func();
            except Exception as e:
                last_error = e;
                is_transient, error_category = self.classify_error( e );
                
                # Don't retry fatal errors
                if not is_transient:
                    self.logger.error( f"Fatal {error_category} error, not retrying: {e}" );
                    raise e;
                
                # Don't retry on last attempt
                if attempt == max_retries - 1:
                    self.logger.error( f"Max retries exceeded for {error_category} error: {e}" );
                    raise e;
                
                wait_time = ( 2 ** attempt ) + ( time.time() % 1 );  # Add jitter
                self.logger.warning( f"Transient {error_category} error (attempt {attempt + 1}/{max_retries}), retrying in {wait_time:.1f}s: {e}" );
                time.sleep( wait_time );
        
        # Shouldn't reach here, but just in case
        raise last_error;


class LocalWhisperEngine( TranscriptionEngine ):
    """
    Local OpenAI Whisper engine for CPU/GPU processing.
    
    This engine uses the open-source Whisper model for local processing,
    providing privacy, cost savings, and offline capability.
    
    Features:
    - Automatic GPU detection and fallback to CPU
    - Multiple model sizes (tiny, base, small, medium, large)
    - Robust error handling with system compatibility checks
    - Optimized settings for different hardware configurations
    """
    
    # Class-level model cache to avoid reloading models
    _model_cache: Dict[str, Any] = {}
    _whisper_available = None
    _torch_available = None
    
    def __init__( self, model_name: str = "base", device: Optional[str] = None, 
                 enable_fallback: bool = True ):
        """
        Initialize Local Whisper engine.
        
        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
            device: Force specific device ("cpu", "cuda", or None for auto-detect)
            enable_fallback: If True, fallback to CPU if GPU fails
        """
        super().__init__()
        
        self.model_name = model_name
        self.requested_device = device
        self.enable_fallback = enable_fallback
        self.model = None
        self.actual_device = "cpu"
        
        # Check system capabilities
        self.capabilities = get_system_capabilities()
        self.config = WhisperConfig()
        
        # Validate model compatibility
        self._validate_setup()
        
        # Initialize if not disabled
        if not self._is_disabled():
            self._initialize_model()
    
    @classmethod
    def _check_whisper_availability(cls) -> Tuple[bool, str]:
        """Check if Whisper is available and working."""
        if cls._whisper_available is not None:
            return cls._whisper_available
            
        try:
            import whisper
            # Test basic functionality
            available_models = whisper.available_models()
            cls._whisper_available = (True, f"Available models: {list(available_models)}")
        except ImportError as e:
            cls._whisper_available = (False, f"Whisper not installed: {e}")
        except Exception as e:
            cls._whisper_available = (False, f"Whisper import error: {e}")
            
        return cls._whisper_available
    
    @classmethod 
    def _check_torch_availability(cls) -> Tuple[bool, str]:
        """Check if PyTorch is available and CUDA status."""
        if cls._torch_available is not None:
            return cls._torch_available
            
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            cuda_devices = torch.cuda.device_count() if cuda_available else 0
            
            info = f"PyTorch {torch.__version__}"
            if cuda_available:
                info += f", CUDA available ({cuda_devices} device(s))"
            else:
                info += ", CUDA not available"
                
            cls._torch_available = (True, info)
        except ImportError as e:
            cls._torch_available = (False, f"PyTorch not installed: {e}")
        except Exception as e:
            cls._torch_available = (False, f"PyTorch error: {e}")
            
        return cls._torch_available
    
    def _is_disabled(self) -> bool:
        """Check if local Whisper is disabled via environment variable."""
        import os
        disabled = os.getenv('SUBSHIFT_DISABLE_LOCAL_WHISPER', '').lower() in ('1', 'true', 'yes')
        if disabled:
            self.logger.info("🚫 Local Whisper disabled via SUBSHIFT_DISABLE_LOCAL_WHISPER")
        return disabled
    
    def _validate_setup(self):
        """Validate system setup and model compatibility."""
        # Check Whisper availability
        whisper_ok, whisper_msg = self._check_whisper_availability()
        if not whisper_ok:
            self.logger.error(f"❌ Whisper validation failed: {whisper_msg}")
            raise RuntimeError(f"Local Whisper unavailable: {whisper_msg}")
            
        # Check PyTorch availability
        torch_ok, torch_msg = self._check_torch_availability()
        if not torch_ok:
            self.logger.error(f"❌ PyTorch validation failed: {torch_msg}")
            raise RuntimeError(f"PyTorch unavailable: {torch_msg}")
            
        # Check model compatibility
        model_ok, model_msg = self.config.validate_model_for_system(
            self.model_name, self.capabilities
        )
        if not model_ok:
            self.logger.warning(f"⚠️  Model {self.model_name} may not be optimal: {model_msg}")
            if self.model_name not in ['tiny', 'base']:  # Only warn for larger models
                self.logger.info(f"💡 Consider using a smaller model like 'base' or 'tiny'")
        
        self.logger.info(f"✅ Whisper validation passed: {whisper_msg}")
        self.logger.info(f"✅ PyTorch validation passed: {torch_msg}")
    
    def _determine_optimal_device(self) -> str:
        """Determine the optimal device for processing."""
        if self.requested_device:
            self.logger.info(f"🎯 Using requested device: {self.requested_device}")
            return self.requested_device
            
        if self.capabilities.torch_cuda_available and self.capabilities.gpus:
            gpu = self.capabilities.gpus[0]
            self.logger.info(f"🚀 Using GPU: {gpu.name} ({gpu.memory_mb/1024:.1f}GB)")
            return "cuda"
        else:
            cpu_info = f"{self.capabilities.cpu_name} ({self.capabilities.cpu_cores} cores)"
            self.logger.info(f"🖥️  Using CPU: {cpu_info}")
            return "cpu"
    
    def _initialize_model(self):
        """Initialize the Whisper model with error handling and fallback."""
        # Check if model is already cached
        cache_key = f"{self.model_name}_{self.actual_device}"
        if cache_key in self._model_cache:
            self.model = self._model_cache[cache_key]
            self.logger.info(f"📦 Using cached Whisper {self.model_name} model")
            return
        
        # Determine device
        self.actual_device = self._determine_optimal_device()
        
        # Import here to avoid issues if not available
        try:
            import whisper
            import torch
        except ImportError as e:
            raise RuntimeError(f"Required dependencies not available: {e}")
        
        # Load model with error handling
        self.logger.info(f"🔄 Loading Whisper {self.model_name} model on {self.actual_device}...")
        
        try:
            # Load model
            self.model = whisper.load_model(
                self.model_name, 
                device=self.actual_device,
                download_root=None  # Use default cache location
            )
            
            # Verify model loaded correctly
            if self.model is None:
                raise RuntimeError("Model loading returned None")
            
            # Cache the model
            cache_key = f"{self.model_name}_{self.actual_device}"
            self._model_cache[cache_key] = self.model
            
            model_info = self.config.get_model_info(self.model_name)
            self.logger.info(f"✅ Whisper {self.model_name} model loaded successfully ({model_info['size_mb']}MB)")
            self.logger.info(f"   Device: {self.actual_device}")
            self.logger.info(f"   Expected performance: ~{model_info['relative_speed']}x real-time")
            
        except Exception as e:
            error_msg = f"Failed to load Whisper {self.model_name} model on {self.actual_device}: {e}"
            
            # Try CPU fallback if requested and not already on CPU
            if self.enable_fallback and self.actual_device != "cpu":
                self.logger.warning(f"⚠️  {error_msg}")
                self.logger.info("🔄 Attempting CPU fallback...")
                
                try:
                    self.actual_device = "cpu"
                    self.model = whisper.load_model(self.model_name, device="cpu")
                    
                    # Cache the fallback model
                    cache_key = f"{self.model_name}_cpu"
                    self._model_cache[cache_key] = self.model
                    
                    self.logger.info(f"✅ Whisper {self.model_name} model loaded on CPU (fallback)")
                    
                except Exception as fallback_error:
                    raise RuntimeError(f"{error_msg}. CPU fallback also failed: {fallback_error}")
            else:
                raise RuntimeError(error_msg)
    
    def transcribe( self, audio_sample: AudioSample ) -> str:
        """
        Transcribe audio sample using local Whisper model.
        
        Args:
            audio_sample: AudioSample object with file path
            
        Returns:
            Cleaned transcript text
        """
        if self._is_disabled():
            raise RuntimeError("Local Whisper is disabled")
            
        if self.model is None:
            raise RuntimeError("Whisper model not initialized")
        
        self.logger.debug( f"Transcribing {audio_sample} with local Whisper {self.model_name}" );
        
        try:
            start_time = time.time()
            
            # Configure transcription options
            transcribe_options = {
                "language": "en",  # Can be None for auto-detection
                "task": "transcribe",
                "fp16": self.actual_device == "cuda",  # Use fp16 on GPU, fp32 on CPU
                "verbose": False,  # Reduce console output
            }
            
            # Add device-specific optimizations
            if self.actual_device == "cpu":
                # CPU optimizations
                transcribe_options["compression_ratio_threshold"] = 2.4
                transcribe_options["logprob_threshold"] = -1.0
                transcribe_options["no_speech_threshold"] = 0.6
            else:
                # GPU optimizations
                transcribe_options["beam_size"] = 5
                transcribe_options["best_of"] = 5
            
            # Perform transcription
            result = self.model.transcribe(
                str(audio_sample.file_path),
                **transcribe_options
            )
            
            # Extract text
            transcript = result.get('text', '')
            if not transcript:
                self.logger.warning(f"Empty transcript from {audio_sample}")
                return ""
            
            # Clean transcript
            cleaned_text = self.clean_transcript(transcript)
            
            # Log performance
            elapsed_time = time.time() - start_time
            self.logger.debug(f"Local Whisper transcript ({elapsed_time:.2f}s): {cleaned_text[:100]}...")
            
            return cleaned_text
            
        except Exception as e:
            self.logger.error( f"Local Whisper transcription failed for {audio_sample}: {e}" );
            
            # Re-raise with more context
            raise RuntimeError(f"Local Whisper transcription failed: {e}") from e
    
    @classmethod
    def get_available_models(cls) -> List[str]:
        """Get list of available Whisper models."""
        try:
            import whisper
            return list(whisper.available_models())
        except Exception:
            return ["tiny", "base", "small", "medium", "large"]  # Fallback list
    
    @classmethod
    def clear_model_cache(cls):
        """Clear the model cache to free memory."""
        cls._model_cache.clear()
        logger = get_logger()
        logger.info("🗑️  Cleared Whisper model cache")


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


def create_transcription_engine( api_name: str, api_key: Optional[str] = None, 
                                model_name: str = "base", device: Optional[str] = None ) -> TranscriptionEngine:
    """
    Factory function to create appropriate transcription engine.
    
    Args:
        api_name: Engine type - "openai", "google", or "local-{model}"
        api_key: API key for the service (not needed for local engines)
        model_name: Whisper model size for local engines (tiny, base, small, medium, large)
        device: Force specific device for local engines ("cpu", "cuda", or None for auto-detect)
        
    Returns:
        Initialized transcription engine
        
    Supported engines:
        - "openai": OpenAI Whisper API (requires api_key)
        - "google": Google Cloud Speech-to-Text API (requires api_key)
        - "local": Local Whisper with auto-detected model (base)
        - "local-tiny": Local Whisper tiny model
        - "local-base": Local Whisper base model
        - "local-small": Local Whisper small model
        - "local-medium": Local Whisper medium model
        - "local-large": Local Whisper large model
    """
    logger = get_logger()
    
    if api_name == "openai":
        if not api_key:
            raise ValueError("OpenAI API key required for 'openai' engine")
        logger.info("🌐 Using OpenAI Whisper API")
        return WhisperEngine( api_key )
        
    elif api_name == "google":
        if not api_key:
            raise ValueError("Google API key required for 'google' engine")
        logger.info("🌐 Using Google Cloud Speech-to-Text API")
        return GoogleSpeechEngine( api_key )
        
    elif api_name.startswith("local"):
        # Parse local engine variants
        if api_name == "local":
            # Default local engine
            model = model_name if model_name else "base"
        elif "-" in api_name:
            # Extract model from engine name (e.g., "local-tiny" -> "tiny")
            model = api_name.split("-", 1)[1]
            if model not in ["tiny", "base", "small", "medium", "large"]:
                raise ValueError(f"Unknown local model: {model}. Use tiny, base, small, medium, or large")
        else:
            raise ValueError(f"Invalid local engine name: {api_name}")
        
        logger.info(f"🖥️  Using local Whisper {model} model")
        
        # Check if local Whisper is disabled
        import os
        if os.getenv('SUBSHIFT_DISABLE_LOCAL_WHISPER', '').lower() in ('1', 'true', 'yes'):
            raise RuntimeError("Local Whisper is disabled via SUBSHIFT_DISABLE_LOCAL_WHISPER environment variable")
        
        return LocalWhisperEngine( model_name=model, device=device )
        
    else:
        available_engines = [
            "openai", "google", "local", "local-tiny", "local-base", 
            "local-small", "local-medium", "local-large"
        ]
        raise ValueError( f"Unknown transcription engine: {api_name}. Available: {available_engines}" );
