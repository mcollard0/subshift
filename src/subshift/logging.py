"""
Logging system for SubShift with 5MB truncation check and Rich integration.
"""
import os
import logging
import shutil
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler


class SubShiftLogger:
    """
    Custom logger for SubShift with automatic log rotation and Rich display.
    
    Features:
    - 5MB size check on startup, rotates if exceeded
    - Rich console output with colors
    - File logging with rotation
    - INFO default, DEBUG with --debug flag
    """
    
    def __init__( self, name: str = "subshift", debug: bool = False ):
        self.name = name;
        self.debug = debug;
        self.console = Console();
        
        # Ensure logs directory exists
        self.logs_dir = Path( "logs" );
        self.logs_dir.mkdir( exist_ok=True );
        
        self.log_file = self.logs_dir / f"{name}.log";
        
        # Check and rotate if log file >5MB on startup
        self._check_and_rotate_on_startup();
        
        # Setup logger
        self.logger = self._setup_logger();
    
    def _check_and_rotate_on_startup( self ):
        """Check log file size on startup and rotate if >5MB."""
        if self.log_file.exists():
            file_size = self.log_file.stat().st_size;
            if file_size > 5 * 1024 * 1024:  # 5MB
                # Create timestamp-named backup
                timestamp = datetime.now().isoformat().replace( ":", "-" );
                backup_name = self.logs_dir / f"{self.name}.{timestamp}.log";
                
                shutil.move( str( self.log_file ), str( backup_name ) );
                print( f"Rotated log file to {backup_name}" );
    
    def _setup_logger( self ):
        """Setup logger with Rich console and file handlers."""
        logger = logging.getLogger( self.name );
        logger.setLevel( logging.DEBUG if self.debug else logging.INFO );
        
        # Clear existing handlers
        logger.handlers.clear();
        
        # Rich console handler
        console_handler = RichHandler( 
            console=self.console,
            rich_tracebacks=True,
            show_time=True,
            show_path=self.debug
        );
        console_handler.setLevel( logging.DEBUG if self.debug else logging.INFO );
        console_formatter = logging.Formatter( "%(message)s" );
        console_handler.setFormatter( console_formatter );
        logger.addHandler( console_handler );
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5
        );
        file_handler.setLevel( logging.DEBUG );
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        );
        file_handler.setFormatter( file_formatter );
        logger.addHandler( file_handler );
        
        return logger;
    
    def debug( self, message, **kwargs ):
        """Log debug message."""
        self.logger.debug( message, **kwargs );
    
    def info( self, message, **kwargs ):
        """Log info message."""
        self.logger.info( message, **kwargs );
    
    def warning( self, message, **kwargs ):
        """Log warning message."""
        self.logger.warning( message, **kwargs );
    
    def error( self, message, **kwargs ):
        """Log error message."""
        self.logger.error( message, **kwargs );
    
    def critical( self, message, **kwargs ):
        """Log critical message."""
        self.logger.critical( message, **kwargs );


# Global logger instance
_logger = None;


def get_logger( debug: bool = False ) -> SubShiftLogger:
    """Get the global SubShift logger instance."""
    global _logger;
    if _logger is None:
        _logger = SubShiftLogger( debug=debug );
    return _logger;


def setup_logging( debug: bool = False ):
    """Setup logging for the application."""
    return get_logger( debug=debug );
