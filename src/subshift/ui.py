"""
Curses-based UI for interactive progress display during synchronization.
"""
import curses
import time
from typing import List

from .align import AlignmentMatch


class CursesUI:
    """
    Simple curses UI with a status bar and match table.
    """
    
    def __init__( self ):
        self.screen = None;
        self.height = 0;
        self.width = 0;
    
    def __enter__( self ):
        self.screen = curses.initscr();
        curses.noecho();
        curses.cbreak();
        self.screen.keypad( True );
        self.height, self.width = self.screen.getmaxyx();
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
    
    def draw_matches( self, matches: List[AlignmentMatch], start_line: int = 3 ):
        line = start_line;
        self.screen.addstr( line, 0, " Sample  |  Audio(m)  |  Sub(m)  |  Similarity  |  Result " );
        line += 1;
        self.screen.hline( line, 0, '-', self.width );
        line += 1;
        
        for m in matches[-( self.height - line - 3 ):]:  # Fit in screen
            result = "PASS" if m.is_match else "FAIL";
            row = f"   {m.audio_sample_index:02d}    |   {m.audio_sample_timestamp/60:6.1f}  |  {m.subtitle_minute:6d}  |   {m.similarity_score:6.2f}    |  {result} ";
            self.screen.addstr( line, 0, row[: self.width - 1 ] );
            line += 1;
        self.screen.refresh();

