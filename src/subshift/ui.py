"""
Curses-based UI for interactive progress display during synchronization.
"""
import curses
import time
from typing import List

from .align import AlignmentMatch


class CursesUI:
    """
    Enhanced curses UI with per-sample progress and time estimates.
    """
    
    def __init__( self ):
        self.screen = None;
        self.height = 0;
        self.width = 0;
        self.start_time = None;
        self.current_step = "Initializing...";
        self.current_sample = 0;
        self.total_samples = 0;
    
    def __enter__( self ):
        self.screen = curses.initscr();
        curses.noecho();
        curses.cbreak();
        self.screen.keypad( True );
        self.height, self.width = self.screen.getmaxyx();
        self.start_time = time.time();
        return self;
    
    def __exit__( self, exc_type, exc, tb ):
        if self.screen:
            self.screen.keypad( False );
            curses.echo();
            curses.nocbreak();
            curses.endwin();
    
    def draw_header( self, title: str ):
        self.screen.clear();
        header = f" SubShift Interactive Monitor — {title} ";
        self.screen.addstr( 0, 0, header[: self.width - 1 ] );
        self.screen.hline( 1, 0, '-', self.width );
    
    def draw_status( self, progress: float, samples_done: int, samples_total: int, elapsed_sec: float ):
        bar_width = max( 10, self.width - 30 );
        fill = int( bar_width * progress );
        bar = '[' + '#' * fill + '-' * ( bar_width - fill ) + ']';
        status = f" {bar} {int( progress * 100 )}%  Samples: {samples_done}/{samples_total}  Elapsed: {int( elapsed_sec )}s ";
        self.screen.addstr( self.height - 2, 0, status[: self.width - 1 ] );
        self.screen.refresh();
    
    def set_step( self, step: str, current_sample: int = 0, total_samples: int = 0 ):
        """Set current processing step and sample counts."""
        self.current_step = step;
        self.current_sample = current_sample;
        self.total_samples = total_samples;
    
    def get_elapsed_time( self ) -> float:
        """Get elapsed time since UI started."""
        if self.start_time is None:
            return 0.0;
        return time.time() - self.start_time;
    
    def estimate_remaining_time( self, progress: float ) -> float:
        """Estimate remaining time based on current progress."""
        if progress <= 0.0:
            return 0.0;
        elapsed = self.get_elapsed_time();
        return ( elapsed / progress ) - elapsed;
    
    def draw_step_info( self, line: int ) -> int:
        """Draw current step information and return next line."""
        elapsed = self.get_elapsed_time();
        step_text = f" Step: {self.current_step} ";
        self.screen.addstr( line, 0, step_text[: self.width - 1 ] );
        line += 1;
        
        if self.total_samples > 0:
            progress = self.current_sample / self.total_samples;
            remaining = self.estimate_remaining_time( progress );
            sample_text = f" Sample Progress: {self.current_sample}/{self.total_samples} ";
            time_text = f" Elapsed: {elapsed:.0f}s | Est. Remaining: {remaining:.0f}s ";
            
            self.screen.addstr( line, 0, sample_text[: self.width - 1 ] );
            line += 1;
            self.screen.addstr( line, 0, time_text[: self.width - 1 ] );
            line += 1;
        
        self.screen.hline( line, 0, '-', self.width );
        return line + 1;
    
    def draw_matches( self, matches: List[AlignmentMatch], start_line: int = 3 ):
        line = start_line;
        
        # Draw step info first
        line = self.draw_step_info( line );
        
        # Draw matches table
        if matches:
            self.screen.addstr( line, 0, " Sample  |  Audio(m)  |  Sub(m)  |  Similarity  |  Result " );
            line += 1;
            self.screen.hline( line, 0, '-', self.width );
            line += 1;
            
            # Show recent matches that fit on screen
            visible_matches = matches[-( self.height - line - 3 ):];  # Fit in screen
            for m in visible_matches:
                result = "PASS" if m.is_match else "FAIL";
                row = f"   {m.audio_sample_index:02d}    |   {m.audio_sample_timestamp/60:6.1f}  |  {m.subtitle_minute:6d}  |   {m.similarity_score:6.2f}    |  {result} ";
                self.screen.addstr( line, 0, row[: self.width - 1 ] );
                line += 1;
        else:
            self.screen.addstr( line, 0, " No matches yet... " );
        
        self.screen.refresh();

