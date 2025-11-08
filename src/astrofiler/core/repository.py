"""
Repository management module for AstroFiler.

This module handles file organization, repository structure management,
and file movement operations.
"""

import os
import shutil
import logging
import configparser

logger = logging.getLogger(__name__)


class RepositoryManager:
    """
    Handles repository file organization and management operations.
    """
    
    def __init__(self):
        """Initialize RepositoryManager with configuration."""
        config = configparser.ConfigParser()
        config.read('astrofiler.ini')
        self.sourceFolder = config.get('DEFAULT', 'source', fallback='.')
        self.repoFolder = config.get('DEFAULT', 'repo', fallback='.')

    def createRepositoryStructure(self):
        """
        Create the standard repository directory structure.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create main directories
            directories = [
                os.path.join(self.repoFolder, 'Light'),
                os.path.join(self.repoFolder, 'Calibrate'),
                os.path.join(self.repoFolder, 'Masters'),
                os.path.join(self.repoFolder, 'Incoming'),
                os.path.join(self.repoFolder, 'Archive'),
                os.path.join(self.repoFolder, 'Processed'),
            ]
            
            for directory in directories:
                os.makedirs(directory, exist_ok=True)
                logger.debug(f"Created directory: {directory}")
            
            logger.info(f"Repository structure created at: {self.repoFolder}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating repository structure: {e}")
            return False

    def organizeFileByType(self, file_path, hdr, new_filename=None):
        """
        Organize a file into the appropriate repository structure based on type.
        
        Args:
            file_path (str): Current path to the file
            hdr: FITS header object
            new_filename (str, optional): New filename to use
            
        Returns:
            str or None: New file path if successful, None if failed
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                return None
            
            # Determine file type and destination
            imagetyp = hdr.get('IMAGETYP', '').upper()
            object_name = hdr.get('OBJECT', 'Unknown')
            telescope = hdr.get('TELESCOP', 'Unknown')
            instrument = hdr.get('INSTRUME', 'Unknown')
            
            # Sanitize names for filesystem
            from .utils import sanitize_filesystem_name
            object_safe = sanitize_filesystem_name(object_name)
            telescope_safe = sanitize_filesystem_name(telescope)
            instrument_safe = sanitize_filesystem_name(instrument)
            
            # Determine destination directory
            if 'LIGHT' in imagetyp:
                # Light frames: Light/{OBJECT}/{TELESCOPE}/{INSTRUMENT}/{DATE}/
                date_str = self._getDateString(hdr)
                dest_dir = os.path.join(
                    self.repoFolder, 'Light', object_safe, 
                    telescope_safe, instrument_safe, date_str
                )
            elif imagetyp in ['BIAS', 'DARK', 'FLAT']:
                # Calibration frames: Calibrate/{TYPE}/{TELESCOPE}/{INSTRUMENT}/
                dest_dir = os.path.join(
                    self.repoFolder, 'Calibrate', imagetyp,
                    telescope_safe, instrument_safe
                )
            else:
                # Unknown type: put in Incoming for manual sorting
                dest_dir = os.path.join(self.repoFolder, 'Incoming')
            
            # Create destination directory
            os.makedirs(dest_dir, exist_ok=True)
            
            # Determine filename
            if new_filename:
                filename = new_filename
            else:
                filename = os.path.basename(file_path)
            
            # Ensure unique filename
            dest_path = os.path.join(dest_dir, filename)
            dest_path = self._ensureUniqueFilename(dest_path)
            
            # Move the file
            shutil.move(file_path, dest_path)
            logger.info(f"Moved file to repository: {dest_path}")
            
            return dest_path
            
        except Exception as e:
            logger.error(f"Error organizing file {file_path}: {e}")
            return None

    def _getDateString(self, hdr):
        """
        Extract date string from FITS header for directory organization.
        
        Args:
            hdr: FITS header object
            
        Returns:
            str: Date string in YYYYMMDD format
        """
        try:
            from datetime import datetime
            
            date_obs = hdr.get('DATE-OBS', '')
            if date_obs:
                # Parse the date string
                date_part = date_obs.split('T')[0]  # Get date part before 'T'
                date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                return date_obj.strftime('%Y%m%d')
            else:
                # Use current date as fallback
                return datetime.now().strftime('%Y%m%d')
                
        except Exception as e:
            logger.error(f"Error parsing date from header: {e}")
            from datetime import datetime
            return datetime.now().strftime('%Y%m%d')

    def _ensureUniqueFilename(self, file_path):
        """
        Ensure filename is unique by adding a counter if necessary.
        
        Args:
            file_path (str): Desired file path
            
        Returns:
            str: Unique file path
        """
        if not os.path.exists(file_path):
            return file_path
        
        base, ext = os.path.splitext(file_path)
        counter = 1
        
        while os.path.exists(f"{base}_{counter:03d}{ext}"):
            counter += 1
        
        return f"{base}_{counter:03d}{ext}"

    def validateRepositoryStructure(self):
        """
        Validate that the repository structure exists and is accessible.
        
        Returns:
            dict: Validation results with status and messages
        """
        results = {
            'valid': True,
            'messages': [],
            'missing_directories': [],
            'permission_issues': []
        }
        
        try:
            # Check if repository root exists
            if not os.path.exists(self.repoFolder):
                results['valid'] = False
                results['messages'].append(f"Repository root does not exist: {self.repoFolder}")
                return results
            
            # Check required directories
            required_dirs = ['Light', 'Calibrate', 'Masters']
            
            for dirname in required_dirs:
                dir_path = os.path.join(self.repoFolder, dirname)
                if not os.path.exists(dir_path):
                    results['missing_directories'].append(dir_path)
                    results['valid'] = False
                elif not os.access(dir_path, os.W_OK):
                    results['permission_issues'].append(dir_path)
                    results['valid'] = False
            
            # Check disk space
            try:
                statvfs = os.statvfs(self.repoFolder)
                free_space_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
                if free_space_gb < 1.0:  # Less than 1GB
                    results['messages'].append(f"Low disk space: {free_space_gb:.2f} GB remaining")
            except (OSError, AttributeError):
                # statvfs not available on Windows
                pass
            
            if results['missing_directories']:
                results['messages'].append(f"Missing directories: {', '.join(results['missing_directories'])}")
            
            if results['permission_issues']:
                results['messages'].append(f"Permission issues: {', '.join(results['permission_issues'])}")
            
            if results['valid']:
                results['messages'].append("Repository structure is valid")
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating repository structure: {e}")
            results['valid'] = False
            results['messages'].append(f"Validation error: {e}")
            return results

    def cleanupRepository(self, dry_run=False, progress_callback=None):
        """
        Clean up repository by removing empty directories and organizing loose files.
        
        Args:
            dry_run (bool): If True, only report what would be done
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: Cleanup results
        """
        results = {
            'empty_dirs_removed': 0,
            'files_organized': 0,
            'errors': [],
            'actions': []
        }
        
        try:
            logger.info(f"Starting repository cleanup (dry_run={dry_run})")
            
            # Find empty directories
            empty_dirs = []
            for root, dirs, files in os.walk(self.repoFolder, topdown=False):
                if not dirs and not files and root != self.repoFolder:
                    empty_dirs.append(root)
            
            # Remove empty directories
            for empty_dir in empty_dirs:
                try:
                    if dry_run:
                        results['actions'].append(f"Would remove empty directory: {empty_dir}")
                    else:
                        os.rmdir(empty_dir)
                        results['actions'].append(f"Removed empty directory: {empty_dir}")
                    results['empty_dirs_removed'] += 1
                except Exception as e:
                    error_msg = f"Error removing directory {empty_dir}: {e}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            # Look for misplaced FITS files in the repository root
            for item in os.listdir(self.repoFolder):
                item_path = os.path.join(self.repoFolder, item)
                if os.path.isfile(item_path) and item.lower().endswith(('.fit', '.fits', '.fts')):
                    try:
                        if dry_run:
                            results['actions'].append(f"Would move misplaced file: {item}")
                        else:
                            # Move to Incoming directory for manual sorting
                            incoming_dir = os.path.join(self.repoFolder, 'Incoming')
                            os.makedirs(incoming_dir, exist_ok=True)
                            dest_path = self._ensureUniqueFilename(os.path.join(incoming_dir, item))
                            shutil.move(item_path, dest_path)
                            results['actions'].append(f"Moved misplaced file to Incoming: {item}")
                        results['files_organized'] += 1
                    except Exception as e:
                        error_msg = f"Error moving file {item}: {e}"
                        results['errors'].append(error_msg)
                        logger.error(error_msg)
            
            if progress_callback:
                progress_callback(100, 100, "Cleanup completed")
            
            logger.info(f"Repository cleanup completed: {results['empty_dirs_removed']} empty dirs, {results['files_organized']} files organized")
            return results
            
        except Exception as e:
            error_msg = f"Error during repository cleanup: {e}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
            return results

    def getRepositoryStats(self):
        """
        Get statistics about the repository contents.
        
        Returns:
            dict: Repository statistics
        """
        stats = {
            'total_files': 0,
            'light_frames': 0,
            'calibration_frames': 0,
            'master_frames': 0,
            'total_size_gb': 0.0,
            'directory_breakdown': {},
            'error_count': 0
        }
        
        try:
            for root, dirs, files in os.walk(self.repoFolder):
                for file in files:
                    if file.lower().endswith(('.fit', '.fits', '.fts')):
                        file_path = os.path.join(root, file)
                        
                        try:
                            # Get file size
                            file_size = os.path.getsize(file_path)
                            stats['total_size_gb'] += file_size / (1024**3)
                            stats['total_files'] += 1
                            
                            # Categorize by directory structure
                            rel_path = os.path.relpath(root, self.repoFolder)
                            path_parts = rel_path.split(os.sep)
                            
                            if path_parts[0] == 'Light':
                                stats['light_frames'] += 1
                            elif path_parts[0] == 'Calibrate':
                                stats['calibration_frames'] += 1
                            elif path_parts[0] == 'Masters':
                                stats['master_frames'] += 1
                            
                            # Directory breakdown
                            category = path_parts[0] if path_parts[0] != '.' else 'Root'
                            if category not in stats['directory_breakdown']:
                                stats['directory_breakdown'][category] = 0
                            stats['directory_breakdown'][category] += 1
                            
                        except Exception as e:
                            stats['error_count'] += 1
                            logger.error(f"Error processing file {file_path}: {e}")
            
            logger.info(f"Repository stats: {stats['total_files']} files, {stats['total_size_gb']:.2f} GB")
            return stats
            
        except Exception as e:
            logger.error(f"Error gathering repository statistics: {e}")
            stats['error_count'] += 1
            return stats

    def backupRepository(self, backup_path, compress=True, progress_callback=None):
        """
        Create a backup of the repository.
        
        Args:
            backup_path (str): Path for the backup file/directory
            compress (bool): Whether to create a compressed backup
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: Backup results
        """
        results = {
            'success': False,
            'backup_path': backup_path,
            'backup_size_gb': 0.0,
            'files_backed_up': 0,
            'error_message': None
        }
        
        try:
            if progress_callback:
                progress_callback(0, 100, "Starting backup...")
            
            if compress:
                # Create compressed backup
                import tarfile
                with tarfile.open(backup_path, 'w:gz') as tar:
                    tar.add(self.repoFolder, arcname=os.path.basename(self.repoFolder))
            else:
                # Create uncompressed copy
                shutil.copytree(self.repoFolder, backup_path, dirs_exist_ok=True)
            
            # Get backup size and file count
            if compress:
                results['backup_size_gb'] = os.path.getsize(backup_path) / (1024**3)
                # For compressed backups, estimate file count from original
                repo_stats = self.getRepositoryStats()
                results['files_backed_up'] = repo_stats['total_files']
            else:
                backup_stats = RepositoryManager()
                backup_stats.repoFolder = backup_path
                stats = backup_stats.getRepositoryStats()
                results['backup_size_gb'] = stats['total_size_gb']
                results['files_backed_up'] = stats['total_files']
            
            results['success'] = True
            
            if progress_callback:
                progress_callback(100, 100, "Backup completed")
            
            logger.info(f"Repository backup completed: {results['backup_size_gb']:.2f} GB, {results['files_backed_up']} files")
            
        except Exception as e:
            error_msg = f"Error creating backup: {e}"
            results['error_message'] = error_msg
            logger.error(error_msg)
        
        return results