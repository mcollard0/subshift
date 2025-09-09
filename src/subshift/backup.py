"""
Backup utility with intelligent file retention based on user rules.
"""
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from .logging import get_logger


class BackupManager:
    """
    Manages backup files with retention policies based on file size.
    
    Rules (per user specification):
    - Files <150KB: Keep up to 50 copies
    - Files ≥150KB: Keep up to 25 copies  
    - Performed before ACP or when modifying subtitles
    - ISO-8601 timestamped copies
    """
    
    def __init__( self, backup_dir: Path = None ):
        self.logger = get_logger();
        self.backup_dir = Path( backup_dir ) if backup_dir else Path( "backup" );
        self.backup_dir.mkdir( exist_ok=True );
        
        # Size thresholds in bytes
        self.size_threshold = 150 * 1024;  # 150KB
        self.max_small_files = 50;         # <150KB files
        self.max_large_files = 25;         # ≥150KB files
    
    def get_backup_filename( self, original_file: Path ) -> str:
        """
        Generate backup filename with ISO-8601 timestamp.
        
        Args:
            original_file: Path to original file
            
        Returns:
            Backup filename with timestamp
        """
        timestamp = datetime.now().isoformat().replace( ":", "-" ).split( "." )[0];  # Remove microseconds
        return f"{original_file.stem}.{timestamp}{original_file.suffix}";
    
    def get_existing_backups( self, original_file: Path ) -> List[Tuple[Path, datetime, int]]:
        """
        Get list of existing backup files for the original file.
        
        Args:
            original_file: Path to original file
            
        Returns:
            List of (backup_path, timestamp, size_bytes) tuples, sorted by timestamp
        """
        backup_pattern = f"{original_file.stem}.????-??-??T??-??-??{original_file.suffix}";
        existing_backups = list( self.backup_dir.glob( backup_pattern ) );
        
        backup_info = [];
        for backup_path in existing_backups:
            try:
                # Extract timestamp from filename
                timestamp_str = backup_path.stem.split( ".", 1 )[1];  # Remove original name part
                timestamp_str = timestamp_str.replace( "-", ":", 2 );  # Fix time part
                timestamp = datetime.fromisoformat( timestamp_str );
                
                # Get file size
                size_bytes = backup_path.stat().st_size;
                
                backup_info.append( ( backup_path, timestamp, size_bytes ) );
                
            except ( ValueError, IndexError, OSError ) as e:
                self.logger.debug( f"Skipping malformed backup file {backup_path}: {e}" );
        
        # Sort by timestamp (oldest first)
        backup_info.sort( key=lambda x: x[1] );
        
        return backup_info;
    
    def apply_retention_policy( self, original_file: Path ):
        """
        Apply retention policy to existing backups.
        
        Removes oldest backups to stay within limits based on file size.
        
        Args:
            original_file: Path to original file (used to determine backup pattern)
        """
        backups = self.get_existing_backups( original_file );
        
        if not backups:
            return;
        
        # Determine retention limit based on file size
        # Use current file size, or average of backups if original doesn't exist
        if original_file.exists():
            current_size = original_file.stat().st_size;
        else:
            sizes = [ size for _, _, size in backups ];
            current_size = sum( sizes ) / len( sizes ) if sizes else 0;
        
        max_backups = self.max_small_files if current_size < self.size_threshold else self.max_large_files;
        
        if len( backups ) <= max_backups:
            return;  # Within limits
        
        # Remove oldest backups
        backups_to_remove = backups[:-max_backups];  # Keep the newest max_backups
        
        for backup_path, timestamp, size in backups_to_remove:
            try:
                backup_path.unlink();
                self.logger.debug( f"Removed old backup: {backup_path.name}" );
            except OSError as e:
                self.logger.warning( f"Could not remove backup {backup_path}: {e}" );
        
        removed_count = len( backups_to_remove );
        if removed_count > 0:
            self.logger.info( f"Removed {removed_count} old backup(s) to enforce retention policy" );
    
    def create_backup( self, file_path: Path ) -> Path:
        """
        Create backup of file with timestamp and apply retention policy.
        
        Args:
            file_path: Path to file to backup
            
        Returns:
            Path to created backup file
        """
        if not file_path.exists():
            raise FileNotFoundError( f"File to backup not found: {file_path}" );
        
        # Generate backup filename
        backup_filename = self.get_backup_filename( file_path );
        backup_path = self.backup_dir / backup_filename;
        
        # Create backup
        try:
            shutil.copy2( file_path, backup_path );
            self.logger.info( f"Created backup: {backup_path.name}" );
        except Exception as e:
            raise RuntimeError( f"Failed to create backup: {e}" );
        
        # Apply retention policy
        self.apply_retention_policy( file_path );
        
        return backup_path;
    
    def backup_before_modification( self, file_path: Path ) -> Path:
        """
        Create backup before modifying a file (convenience method).
        
        Args:
            file_path: Path to file about to be modified
            
        Returns:
            Path to created backup file
        """
        self.logger.debug( f"Creating pre-modification backup of {file_path}" );
        return self.create_backup( file_path );
    
    def get_backup_stats( self ) -> dict:
        """Get statistics about backup directory."""
        if not self.backup_dir.exists():
            return { 'total_backups': 0, 'total_size': 0 };
        
        backup_files = list( self.backup_dir.iterdir() );
        total_backups = len( backup_files );
        total_size = sum( f.stat().st_size for f in backup_files if f.is_file() );
        
        # Categorize by size
        small_files = 0;
        large_files = 0;
        
        for f in backup_files:
            if f.is_file():
                size = f.stat().st_size;
                if size < self.size_threshold:
                    small_files += 1;
                else:
                    large_files += 1;
        
        stats = {
            'total_backups': total_backups,
            'total_size': total_size,
            'small_files': small_files,  # <150KB
            'large_files': large_files,  # ≥150KB
            'backup_dir': str( self.backup_dir ),
            'size_threshold': self.size_threshold,
            'max_small_files': self.max_small_files,
            'max_large_files': self.max_large_files
        };
        
        return stats;
    
    def cleanup_empty_backups( self ):
        """Remove any empty or corrupted backup files."""
        if not self.backup_dir.exists():
            return;
        
        removed_count = 0;
        
        for backup_file in self.backup_dir.iterdir():
            if backup_file.is_file():
                try:
                    if backup_file.stat().st_size == 0:
                        backup_file.unlink();
                        removed_count += 1;
                        self.logger.debug( f"Removed empty backup: {backup_file.name}" );
                except OSError as e:
                    self.logger.warning( f"Could not check/remove backup {backup_file}: {e}" );
        
        if removed_count > 0:
            self.logger.info( f"Cleaned up {removed_count} empty backup files" );


# Global backup manager instance
_backup_manager = None;


def get_backup_manager( backup_dir: Path = None ) -> BackupManager:
    """Get the global backup manager instance."""
    global _backup_manager;
    if _backup_manager is None:
        _backup_manager = BackupManager( backup_dir );
    return _backup_manager;


def create_backup( file_path: Path, backup_dir: Path = None ) -> Path:
    """
    Convenience function to create a backup file.
    
    Args:
        file_path: Path to file to backup
        backup_dir: Optional backup directory (defaults to ./backup)
        
    Returns:
        Path to created backup file
    """
    manager = get_backup_manager( backup_dir );
    return manager.create_backup( file_path );
