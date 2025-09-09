"""
Main subtitle synchronization controller that orchestrates the entire process.
"""
import time
from pathlib import Path
from typing import List, Optional

from .audio import AudioProcessor, AudioSample, AdaptiveSamplingCoordinator
from .transcribe import create_transcription_engine, TranscriptionEngine
from .subtitles import SubtitleProcessor
from .align import AlignmentEngine, AlignmentMatch
from .offset import OffsetCalculator
from .logging import get_logger


class SubtitleSynchronizer:
    """
    Main controller for subtitle synchronization process.
    
    Orchestrates:
    1. Audio extraction and sampling
    2. AI transcription
    3. Subtitle parsing and indexing
    4. Text alignment using Levenshtein distance
    5. Offset calculation and interpolation
    6. Subtitle correction and backup
    """
    
    def __init__( 
        self, 
        video_file: Path,
        subtitle_file: Path,
        api_engine: str = "openai",
        api_key: str = "",
        search_window: int = 20,
        similarity_threshold: float = 0.7,
        min_chars: int = 40,
        samples: int = 4,
        debug: bool = False,
        use_curses: bool = False,
        dry_run: bool = False,
        remove_sdh: bool = False
    ):
        self.video_file = Path( video_file );
        self.subtitle_file = Path( subtitle_file );
        self.api_engine = api_engine;
        self.api_key = api_key;
        self.search_window = search_window;
        self.similarity_threshold = similarity_threshold;
        self.min_chars = min_chars;
        self.samples = samples;
        self.debug = debug;
        self.use_curses = use_curses;
        self.dry_run = dry_run;
        self.remove_sdh = remove_sdh;
        
        self.logger = get_logger( debug=debug );
        
        # Initialize components
        self.audio_processor = AudioProcessor( debug=debug );
        self.transcription_engine = create_transcription_engine( api_engine, api_key );
        self.subtitle_processor = SubtitleProcessor( min_chars=min_chars );
        self.alignment_engine = AlignmentEngine( 
            similarity_threshold=similarity_threshold,
            search_window=search_window,
            min_chars=min_chars
        );
        self.offset_calculator = OffsetCalculator();
        self.adaptive_sampling = AdaptiveSamplingCoordinator( debug=debug );
        
        # Results storage
        self.audio_samples: List[AudioSample] = [];
        self.alignment_matches: List[AlignmentMatch] = [];
        self.current_phase = "initial";  # Track sampling phase
    
    def extract_audio_samples( self ) -> List[AudioSample]:
        """Extract audio samples from video file using adaptive sampling."""
        self.logger.info( "=== STEP 1: AUDIO EXTRACTION (ADAPTIVE) ===" );
        
        # Use adaptive sampling if no specific sample count requested
        if self.samples <= 4:  # Default or low sample count - use adaptive
            # Start with initial phase sampling
            recommended_samples = 12 if self.current_phase == "initial" else self.samples;
            self.logger.info( f"Adaptive sampling: {self.current_phase} phase, {recommended_samples} samples" );
        else:
            # User specified sample count - respect it
            recommended_samples = self.samples;
            self.logger.info( f"User-specified sampling: {recommended_samples} samples" );
        
        self.audio_samples = self.audio_processor.extract_audio_samples( 
            self.video_file, 
            num_samples=recommended_samples
        );
        
        if not self.audio_samples:
            raise RuntimeError( "Failed to extract any audio samples" );
        
        # Log cost estimate for transparency
        cost = self.adaptive_sampling.get_cost_estimate( len( self.audio_samples ) );
        self.logger.info( f"Successfully extracted {len( self.audio_samples )} audio samples (est. cost: ${cost:.3f})" );
        return self.audio_samples;
    
    def transcribe_audio_samples( self ) -> List[AudioSample]:
        """Transcribe audio samples using AI."""
        self.logger.info( "=== STEP 2: AI TRANSCRIPTION ===" );
        
        if not self.audio_samples:
            raise RuntimeError( "No audio samples to transcribe. Run extract_audio_samples first." );
        
        transcribed_count = 0;
        
        for sample in self.audio_samples:
            try:
                sample.transcription = self.transcription_engine.transcribe( sample );
                if sample.transcription:
                    transcribed_count += 1;
                    self.logger.debug( f"Sample {sample.index} transcribed: " \
                                     f"'{sample.transcription[:50]}...'" );
                else:
                    self.logger.warning( f"Sample {sample.index} transcription failed" );
                    
            except Exception as e:
                self.logger.error( f"Transcription failed for sample {sample.index}: {e}" );
        
        if transcribed_count == 0:
            raise RuntimeError( "Failed to transcribe any audio samples" );
        
        self.logger.info( f"Successfully transcribed {transcribed_count}/{len( self.audio_samples )} samples" );
        return self.audio_samples;
    
    def parse_subtitles( self ) -> SubtitleProcessor:
        """Parse and index subtitle file."""
        self.logger.info( "=== STEP 3: SUBTITLE PROCESSING ===" );
        
        # Parse subtitle file
        subtitle_entries = self.subtitle_processor.parse_subtitle_file( self.subtitle_file );
        if not subtitle_entries:
            raise RuntimeError( "Failed to parse subtitle file" );
        
        # Create minute-based index
        self.subtitle_processor.create_minute_index();
        
        # Display stats
        stats = self.subtitle_processor.get_subtitle_stats();
        self.logger.info( f"Parsed {stats['total_entries']} subtitles " \
                         f"({stats['duration_minutes']:.1f} minutes)" );
        self.logger.info( f"Found {stats['valid_minutes']} minutes with ≥{self.min_chars} characters" );
        
        return self.subtitle_processor;
    
    def align_transcripts( self ) -> List[AlignmentMatch]:
        """Align AI transcripts with subtitle text."""
        self.logger.info( "=== STEP 4: TEXT ALIGNMENT ===" );
        
        if not self.audio_samples or not self.subtitle_processor.subtitle_entries:
            raise RuntimeError( "Missing audio samples or subtitles. Run previous steps first." );
        
        # Filter samples with transcriptions
        transcribed_samples = [ sample for sample in self.audio_samples if sample.transcription ];
        
        if not transcribed_samples:
            raise RuntimeError( "No transcribed audio samples available for alignment" );
        
        # Perform alignment
        self.alignment_matches = self.alignment_engine.align_samples( 
            transcribed_samples, 
            self.subtitle_processor 
        );
        
        # Display results
        if self.debug:
            self.alignment_engine.display_matches( self.alignment_matches, debug=True );
        
        # Check for successful matches
        successful_matches = self.alignment_engine.get_successful_matches( self.alignment_matches );
        if not successful_matches:
            self.logger.warning( "No successful alignments found. Consider:" );
            self.logger.warning( f"- Lowering similarity threshold (current: {self.similarity_threshold:.1%})" );
            self.logger.warning( f"- Increasing search window (current: {self.search_window}m)" );
            self.logger.warning( f"- Checking video/subtitle sync quality" );
            
        return self.alignment_matches;
    
    def calculate_offsets( self ) -> List:
        """Calculate time offsets from alignment matches."""
        self.logger.info( "=== STEP 5: OFFSET CALCULATION & ADAPTIVE ANALYSIS ===" );
        
        if not self.alignment_matches:
            raise RuntimeError( "No alignment matches available. Run align_transcripts first." );
        
        # Calculate offsets from successful matches
        offsets = self.offset_calculator.calculate_sample_offsets( self.alignment_matches );
        
        if not offsets:
            raise RuntimeError( "No successful matches found for offset calculation" );
        
        # Adaptive analysis: Check if we need different sampling strategy
        if self.samples <= 4 and len( offsets ) >= 3:  # Only for adaptive mode with sufficient data
            offset_values = [ abs( offset.offset_seconds ) for offset in offsets ];
            success_rate = len( [ match for match in self.alignment_matches if match.is_match ] ) / len( self.alignment_matches );
            
            # Analyze timing consistency
            consistency = self.adaptive_sampling.analyze_timing_consistency( offset_values );
            recommended_samples = self.adaptive_sampling.recommend_sample_count( consistency, success_rate );
            current_samples = len( self.audio_samples );
            
            self.logger.info( f"\n=== ADAPTIVE SAMPLING ANALYSIS ===" );
            self.logger.info( f"Timing consistency: {consistency}" );
            self.logger.info( f"Success rate: {success_rate:.1%}" );
            self.logger.info( f"Current samples: {current_samples}, Recommended: {recommended_samples}" );
            
            # Log cost implications
            current_cost = self.adaptive_sampling.get_cost_estimate( current_samples );
            recommended_cost = self.adaptive_sampling.get_cost_estimate( recommended_samples );
            cost_diff = recommended_cost - current_cost;
            
            if cost_diff > 0.01:  # Significant cost difference
                self.logger.info( f"Cost impact: ${current_cost:.3f} -> ${recommended_cost:.3f} (+${cost_diff:.3f})" );
            elif cost_diff < -0.01:
                self.logger.info( f"Cost savings: ${current_cost:.3f} -> ${recommended_cost:.3f} (${abs(cost_diff):.3f} saved)" );
            
            # Update phase for future runs (learning)
            if consistency == "consistent":
                self.current_phase = "consistent";
            elif consistency == "inconsistent":
                self.current_phase = "inconsistent";
            else:
                self.current_phase = "moderate";
            
            self.logger.info( f"Next run will use '{self.current_phase}' sampling strategy" );
        
        # Display offset summary
        self.offset_calculator.display_offset_summary();
        
        return offsets;
    
    def apply_corrections( self ) -> Path:
        """Apply calculated corrections to subtitle file."""
        self.logger.info( "=== STEP 6: SUBTITLE CORRECTION ===" );
        
        if not self.offset_calculator.offsets:
            raise RuntimeError( "No offsets calculated. Run calculate_offsets first." );
        
        # Apply corrections and save
        corrected_file = self.offset_calculator.apply_corrections( 
            self.subtitle_file,
            dry_run=self.dry_run
        );
        
        return corrected_file;
    
    def remove_sdh_content( self, subtitle_file: Path ) -> Path:
        """Remove SDH (Sound Description for Hearing Impaired) content from subtitle file."""
        self.logger.info( "=== STEP 7: SDH REMOVAL ===" );
        
        from .sdh import SDHRemover;
        
        sdh_remover = SDHRemover( self.api_engine, self.api_key );
        
        if not self.dry_run:
            cleaned_file = sdh_remover.remove_sdh_from_file( 
                subtitle_file,
                use_ai=True  # Use AI analysis for better accuracy
            );
            self.logger.info( f"SDH removal completed. Cleaned file: {cleaned_file}" );
            return cleaned_file;
        else:
            cost_info = sdh_remover.estimate_cost( subtitle_file );
            self.logger.info( f"Dry run: SDH removal cost estimate: ${cost_info.get('estimated_cost_usd', 0):.4f}" );
            return subtitle_file;
    
    def cleanup( self ):
        """Clean up temporary files."""
        self.logger.debug( "Cleaning up temporary files" );
        
        if self.audio_samples:
            self.audio_processor.cleanup_samples( self.audio_samples );
    
    def run( self ) -> bool:
        """
        Run the complete subtitle synchronization process.
        
        Returns:
            True if successful, False if failed
        """
        if self.use_curses:
            return self._run_with_curses();
        else:
            return self._run_normal();
    
    def _run_with_curses( self ) -> bool:
        """Run synchronization with curses UI."""
        from .ui import CursesUI;
        
        try:
            with CursesUI() as ui:
                ui.draw_header( "SubShift Synchronization" );
                ui.set_step( "Initializing...", 0, 0 );
                ui.draw_matches( [] );
                
                # Step 1: Extract audio samples
                ui.set_step( "Extracting audio samples...", 0, 0 );
                ui.draw_matches( [] );
                self.extract_audio_samples();
                
                # Step 2: Transcribe audio using AI
                total_samples = len( self.audio_samples );
                for i, sample in enumerate( self.audio_samples, 1 ):
                    ui.set_step( "Transcribing audio samples...", i, total_samples );
                    ui.draw_matches( self.alignment_matches );
                    
                    sample.transcription = self.transcription_engine.transcribe( sample );
                
                # Step 3: Parse and index subtitles
                ui.set_step( "Processing subtitles...", 0, 0 );
                ui.draw_matches( self.alignment_matches );
                self.parse_subtitles();
                
                # Step 4: Align transcripts with subtitles
                ui.set_step( "Aligning text with subtitles...", 0, 0 );
                ui.draw_matches( self.alignment_matches );
                self.align_transcripts();
                
                # Step 5: Calculate time offsets
                ui.set_step( "Calculating time corrections...", 0, 0 );
                ui.draw_matches( self.alignment_matches );
                self.calculate_offsets();
                
                # Step 6: Apply corrections to subtitle file
                ui.set_step( "Applying corrections...", 0, 0 );
                ui.draw_matches( self.alignment_matches );
                corrected_file = self.apply_corrections();
                
                # Step 7: Remove SDH if requested
                final_file = corrected_file;
                if self.remove_sdh:
                    ui.set_step( "Removing SDH content...", 0, 0 );
                    ui.draw_matches( self.alignment_matches );
                    final_file = self.remove_sdh_content( corrected_file );
                
                # Success!
                ui.set_step( "Synchronization Complete!", 0, 0 );
                ui.draw_matches( self.alignment_matches );
                
                # Show final results for a moment
                time.sleep( 2 );
                
            return self._log_final_results( final_file, corrected_file );
            
        except Exception as e:
            self.logger.error( f"Subtitle synchronization failed: {e}" );
            if self.debug:
                raise;
            return False;
            
        finally:
            self.cleanup();
    
    def _run_normal( self ) -> bool:
        """Run synchronization with normal logging."""
        try:
            self.logger.info( "Starting SubShift subtitle synchronization" );
            self.logger.info( f"Media: {self.video_file}" );
            self.logger.info( f"Subtitles: {self.subtitle_file}" );
            self.logger.info( f"Engine: {self.api_engine}" );
            self.logger.info( f"Similarity threshold: {self.similarity_threshold:.1%}" );
            self.logger.info( f"Search window: {self.search_window} minutes" );
            
            # Step 1: Extract audio samples
            self.extract_audio_samples();
            
            # Step 2: Transcribe audio using AI
            self.transcribe_audio_samples();
            
            # Step 3: Parse and index subtitles
            self.parse_subtitles();
            
            # Step 4: Align transcripts with subtitles
            self.align_transcripts();
            
            # Step 5: Calculate time offsets
            self.calculate_offsets();
            
            # Step 6: Apply corrections to subtitle file
            corrected_file = self.apply_corrections();
            
            # Step 7: Remove SDH if requested
            final_file = corrected_file;
            if self.remove_sdh:
                final_file = self.remove_sdh_content( corrected_file );
            
            return self._log_final_results( final_file, corrected_file );
            
        except Exception as e:
            self.logger.error( f"Subtitle synchronization failed: {e}" );
            if self.debug:
                raise;
            return False;
            
        finally:
            # Always cleanup temporary files
            self.cleanup();
    
    def _log_final_results( self, final_file: Path, corrected_file: Path ) -> bool:
        """Log final results and statistics."""
        self.logger.info( "\n=== SYNCHRONIZATION COMPLETE ===" );
        
        if not self.dry_run:
            self.logger.info( f"✓ Final subtitles saved to: {final_file}" );
            if self.remove_sdh:
                self.logger.info( f"✓ Synchronized subtitles: {corrected_file}" );
            self.logger.info( f"✓ Original backed up to: backup/" );
        else:
            self.logger.info( f"✓ Dry run completed - no files modified" );
        
        # Display final statistics
        stats = self.alignment_engine.calculate_alignment_stats( self.alignment_matches );
        if stats:
            self.logger.info( f"✓ Success rate: {stats['success_rate']:.1%}" );
            self.logger.info( f"✓ Average similarity: {stats['avg_similarity']:.1%}" );
        
        offset_stats = self.offset_calculator.get_offset_stats();
        if offset_stats:
            self.logger.info( f"✓ Average offset: {offset_stats['avg_offset']:.1f}s" );
        
        return True;
            
