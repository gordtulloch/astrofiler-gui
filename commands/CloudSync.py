#!/usr/bin/env python3
"""
CloudSync.py - Command line utility for cloud synchronization

This script performs cloud synchronization operations using the configured sync profile.
It can perform backup sync, complete sync, or analyze cloud storage from the command line.

Usage:
    python CloudSync.py [options]

Options:
    -h, --help       Show this help message and exit
    -v, --verbose    Enable verbose logging
    -c, --config     Path to configuration file (default: astrofiler.ini)
    -p, --profile    Override sync profile (backup|complete)
    -a, --analyze    Only analyze cloud storage, don't sync
    -y, --yes        Skip confirmation prompts (auto-confirm)

Sync Profiles:
    backup      Upload local files to cloud (one-way backup)
    complete    Bidirectional sync (download missing + upload new)

Requirements:
    - astrofiler.ini configuration file with cloud settings
    - Valid Google Cloud Storage credentials
    - Configured bucket URL and repository path

Example:
    # Sync using configured profile
    python CloudSync.py
    
    # Backup sync with verbose output
    python CloudSync.py -p backup -v
    
    # Complete sync with auto-confirm
    python CloudSync.py -p complete -y
    
    # Analyze cloud storage only
    python CloudSync.py -a
"""

import sys
import os
import argparse
import logging
import configparser
from datetime import datetime

# Add the parent directory to the path to import astrofiler modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_logging(verbose=False):
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def load_config(config_path='astrofiler.ini'):
    """Load configuration from file"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

def get_cloud_config(config):
    """Extract cloud configuration from config file"""
    try:
        cloud_config = {
            'bucket_url': config.get('DEFAULT', 'bucket_url', fallback=''),
            'auth_file_path': config.get('DEFAULT', 'auth_file_path', fallback=''),
            'sync_profile': config.get('DEFAULT', 'sync_profile', fallback='complete')
        }
        
        # Validate required settings
        if not cloud_config['bucket_url']:
            raise ValueError("Bucket URL not configured. Please set 'bucket_url' in astrofiler.ini")
        
        if not cloud_config['auth_file_path']:
            raise ValueError("Authentication file path not configured. Please set 'auth_file_path' in astrofiler.ini")
        
        if not os.path.exists(cloud_config['auth_file_path']):
            raise ValueError(f"Authentication file not found: {cloud_config['auth_file_path']}")
        
        return cloud_config
        
    except Exception as e:
        raise ValueError(f"Invalid cloud configuration: {e}")

def validate_bucket_access(cloud_config):
    """Validate that we can access the cloud bucket"""
    from ui.cloud_sync_dialog import _get_gcs_client
    
    try:
        # Extract bucket name
        bucket_url = cloud_config['bucket_url']
        if bucket_url.startswith('gs://'):
            bucket_name = bucket_url.replace('gs://', '').rstrip('/')
        else:
            bucket_name = bucket_url.rstrip('/')
        
        # Test connection
        auth_info = {'auth_string': cloud_config['auth_file_path']}
        client = _get_gcs_client(auth_info)
        bucket = client.bucket(bucket_name)
        
        # Try to list objects to test access
        list(bucket.list_blobs(max_results=1))
        
        logging.info(f"Successfully validated access to bucket: {bucket_name}")
        return True
        
    except Exception as e:
        raise Exception(f"Failed to access cloud bucket: {e}")

def perform_analysis(cloud_config):
    """Perform cloud storage analysis"""
    from ui.cloud_sync_dialog import list_gcs_bucket_files
    from astrofiler_db import fitsFile, setup_database
    
    logging.info("Starting cloud storage analysis...")
    
    # Setup database
    setup_database()
    
    # Extract bucket name
    bucket_url = cloud_config['bucket_url']
    if bucket_url.startswith('gs://'):
        bucket_name = bucket_url.replace('gs://', '').rstrip('/')
    else:
        bucket_name = bucket_url.rstrip('/')
    
    # Get cloud file list
    auth_info = {'auth_string': cloud_config['auth_file_path']}
    cloud_files = list_gcs_bucket_files(bucket_name, auth_info)
    
    logging.info(f"Found {len(cloud_files)} files in cloud storage")
    
    # Get database statistics
    total_db_files = fitsFile.select().count()
    files_with_cloud_url = fitsFile.select().where(
        (fitsFile.fitsFileCloudURL.is_null(False)) & 
        (fitsFile.fitsFileCloudURL != "")
    ).count()
    files_without_cloud_url = total_db_files - files_with_cloud_url
    
    # Report analysis
    print(f"\n{'='*60}")
    print(f"CLOUD SYNC ANALYSIS REPORT")
    print(f"{'='*60}")
    print(f"Configuration:")
    print(f"  Bucket URL: {cloud_config['bucket_url']}")
    print(f"  Sync Profile: {cloud_config['sync_profile']}")
    print(f"  Auth File: {cloud_config['auth_file_path']}")
    print(f"\nCloud Storage:")
    print(f"  Files in bucket: {len(cloud_files)}")
    print(f"  Total size: {sum(f.get('size', 0) for f in cloud_files):,} bytes")
    print(f"\nLocal Database:")
    print(f"  Total FITS files: {total_db_files}")
    print(f"  Files with cloud URLs: {files_with_cloud_url}")
    print(f"  Files without cloud URLs: {files_without_cloud_url}")
    print(f"\nSync Status:")
    if cloud_config['sync_profile'] == 'backup':
        print(f"  Backup Sync: {files_without_cloud_url} files ready to upload")
    elif cloud_config['sync_profile'] == 'complete':
        print(f"  Complete Sync: {files_without_cloud_url} files ready to upload")
        print(f"  Complete Sync: Analysis of missing local files requires sync operation")
    print(f"{'='*60}")

def perform_sync(cloud_config, sync_profile, auto_confirm=False):
    """Perform the actual sync operation"""
    from ui.cloud_sync_dialog import CloudSyncDialog
    from astrofiler_db import setup_database
    import configparser
    
    logging.info(f"Starting {sync_profile} sync...")
    
    # Setup database
    setup_database()
    
    # Get repository path
    config = configparser.ConfigParser()
    config.read('astrofiler.ini')
    repo_path = config.get('DEFAULT', 'repo', fallback='')
    
    if not repo_path or not os.path.exists(repo_path):
        raise ValueError("Repository path is not configured or does not exist")
    
    # Confirmation prompt
    if not auto_confirm:
        operation_desc = {
            'backup': f"Backup Sync: Upload local files to {cloud_config['bucket_url']}",
            'complete': f"Complete Sync: Bidirectional sync with {cloud_config['bucket_url']}",
            'ondemand': f"On Demand Sync: Upload and delete soft-deleted files to {cloud_config['bucket_url']}"
        }
        
        print(f"\nAbout to perform: {operation_desc.get(sync_profile, sync_profile)}")
        print(f"Repository: {repo_path}")
        
        response = input("Continue? (y/N): ").strip().lower()
        if response != 'y':
            print("Operation cancelled.")
            return
    
    # Create a minimal cloud sync dialog for command-line use
    class CommandLineProgress:
        """Simple progress callback for command-line operations"""
        def __init__(self):
            self.current = 0
            self.total = 0
            self.last_percent = -1
            
        def update(self, current, total, message=""):
            self.current = current
            self.total = total if total > 0 else 1
            percent = int((current / self.total) * 100)
            
            if percent != self.last_percent or message:
                if message:
                    print(f"[{percent:3d}%] {message}")
                else:
                    print(f"[{percent:3d}%] Processing... ({current}/{self.total})")
                self.last_percent = percent
    
    # Perform sync based on profile
    try:
        if sync_profile == 'backup':
            perform_backup_sync_cli(cloud_config, repo_path)
        elif sync_profile == 'complete':
            perform_complete_sync_cli(cloud_config, repo_path)
        elif sync_profile == 'ondemand':
            perform_ondemand_sync_cli(cloud_config, repo_path)
        else:
            raise ValueError(f"Unknown sync profile: {sync_profile}")
            
        logging.info(f"{sync_profile.capitalize()} sync completed successfully")
        
    except Exception as e:
        logging.error(f"Sync operation failed: {e}")
        raise

def perform_backup_sync_cli(cloud_config, repo_path):
    """Perform backup sync from command line"""
    from ui.cloud_sync_dialog import upload_file_to_backup
    from astrofiler_db import fitsFile
    
    # Get bucket info
    bucket_url = cloud_config['bucket_url']
    if bucket_url.startswith('gs://'):
        bucket_name = bucket_url.replace('gs://', '').rstrip('/')
    else:
        bucket_name = bucket_url.rstrip('/')
    
    auth_info = {'auth_string': cloud_config['auth_file_path']}
    
    # Get files without cloud URLs (including soft-deleted files)
    fits_files = list(fitsFile.select().where(
        (fitsFile.fitsFileName.is_null(False)) &
        ((fitsFile.fitsFileCloudURL.is_null(True)) | (fitsFile.fitsFileCloudURL == ""))
    ))
    
    print(f"Found {len(fits_files)} files to backup")
    
    uploaded_count = 0
    updated_count = 0
    error_count = 0
    
    for i, fits_file in enumerate(fits_files):
        try:
            print(f"[{i+1:3d}/{len(fits_files)}] {os.path.basename(fits_file.fitsFileName)}")
            
            # Get relative path
            full_path = fits_file.fitsFileName
            if full_path.startswith(repo_path):
                relative_path = os.path.relpath(full_path, repo_path)
            else:
                relative_path = os.path.basename(full_path)
            
            # Check if file exists
            if not os.path.exists(full_path):
                logging.warning(f"File not found: {full_path}")
                error_count += 1
                continue
            
            # Upload
            success, cloud_url, message = upload_file_to_backup(
                bucket_name, auth_info, full_path, relative_path
            )
            
            if success:
                fits_file.fitsFileCloudURL = cloud_url
                fits_file.save()
                updated_count += 1
                
                # Check if we actually uploaded (vs already existed)
                if "uploaded" in message.lower():
                    uploaded_count += 1
                
                # Delete local file if it's soft-deleted, but verify cloud backup first
                if fits_file.fitsFileSoftDelete:
                    try:
                        # Verify file exists in cloud before deleting
                        from ui.cloud_sync_dialog import check_file_exists_in_gcs
                        from astrofiler_cloud import _get_gcs_client
                        
                        client = _get_gcs_client(auth_info)
                        gcs_object_name = relative_path.replace('\\', '/')
                        
                        if check_file_exists_in_gcs(client, bucket_name, gcs_object_name):
                            # File verified in cloud, safe to delete locally
                            os.remove(full_path)
                            print(f"    → Uploaded and deleted soft-deleted file after cloud verification")
                        else:
                            logging.error(f"SAFETY CHECK FAILED: File not found in cloud, keeping local copy: {relative_path}")
                            print(f"    → Uploaded (cloud verification failed, keeping local copy)")
                    except OSError as e:
                        logging.warning(f"Failed to delete soft-deleted file {relative_path}: {e}")
                        print(f"    → Uploaded (failed to delete local copy)")
                    except Exception as e:
                        logging.error(f"Cloud verification failed for {relative_path}, keeping local copy: {e}")
                        print(f"    → Uploaded (cloud verification failed, keeping local copy)")
                elif "uploaded" in message.lower():
                    print(f"    → Uploaded")
                else:
                    print(f"    → Already exists")
            else:
                logging.error(f"Failed to upload {relative_path}: {message}")
                error_count += 1
                
        except Exception as e:
            logging.error(f"Error processing {fits_file.fitsFileName}: {e}")
            error_count += 1
    
    print(f"\nBackup sync completed:")
    print(f"  Files processed: {len(fits_files)}")
    print(f"  Files uploaded: {uploaded_count}")
    print(f"  Database records updated: {updated_count}")
    print(f"  Errors: {error_count}")

def perform_ondemand_sync_cli(cloud_config, repo_path):
    """Perform on-demand sync from command line - upload and delete soft-deleted files"""
    from ui.cloud_sync_dialog import upload_file_to_backup
    from astrofiler_db import fitsFile
    
    # Get bucket info
    bucket_url = cloud_config['bucket_url']
    if bucket_url.startswith('gs://'):
        bucket_name = bucket_url.replace('gs://', '').rstrip('/')
    else:
        bucket_name = bucket_url.rstrip('/')
    
    auth_info = {'auth_string': cloud_config['auth_file_path']}
    
    # Get soft-deleted files
    soft_deleted_files = list(fitsFile.select().where(
        (fitsFile.fitsFileName.is_null(False)) &
        (fitsFile.fitsFileSoftDelete == True)
    ))
    
    print(f"Found {len(soft_deleted_files)} soft-deleted files to upload and delete")
    
    if len(soft_deleted_files) == 0:
        print("No soft-deleted files found. Nothing to do.")
        return
    
    uploaded_count = 0
    deleted_count = 0
    updated_count = 0
    error_count = 0
    
    for i, fits_file in enumerate(soft_deleted_files):
        try:
            print(f"[{i+1:3d}/{len(soft_deleted_files)}] {os.path.basename(fits_file.fitsFileName)}")
            
            # Get relative path
            full_path = fits_file.fitsFileName
            if full_path.startswith(repo_path):
                relative_path = os.path.relpath(full_path, repo_path)
            else:
                relative_path = os.path.basename(full_path)
            
            # Check if file exists
            if not os.path.exists(full_path):
                logging.warning(f"Soft-deleted file not found: {full_path}")
                error_count += 1
                continue
            
            # Upload
            success, cloud_url, message = upload_file_to_backup(
                bucket_name, auth_info, full_path, relative_path
            )
            
            if success:
                fits_file.fitsFileCloudURL = cloud_url
                fits_file.save()
                updated_count += 1
                
                # Check if we actually uploaded (vs already existed)
                if "uploaded" in message.lower():
                    uploaded_count += 1
                
                # Verify cloud backup before deleting local file
                try:
                    from ui.cloud_sync_dialog import check_file_exists_in_gcs
                    from astrofiler_cloud import _get_gcs_client
                    
                    client = _get_gcs_client(auth_info)
                    gcs_object_name = relative_path.replace('\\', '/')
                    
                    if check_file_exists_in_gcs(client, bucket_name, gcs_object_name):
                        # File verified in cloud, safe to delete locally
                        os.remove(full_path)
                        deleted_count += 1
                        print(f"    → Uploaded and deleted after cloud verification")
                    else:
                        logging.error(f"SAFETY CHECK FAILED: File not found in cloud, keeping local copy: {relative_path}")
                        print(f"    → Uploaded (cloud verification failed, keeping local copy)")
                except OSError as e:
                    logging.warning(f"Failed to delete soft-deleted file {relative_path}: {e}")
                    print(f"    → Uploaded (failed to delete local copy)")
                except Exception as e:
                    logging.error(f"Cloud verification failed for {relative_path}, keeping local copy: {e}")
                    print(f"    → Uploaded (cloud verification failed, keeping local copy)")
            else:
                logging.error(f"Failed to upload {relative_path}: {message}")
                error_count += 1
                
        except Exception as e:
            logging.error(f"Error processing {fits_file.fitsFileName}: {e}")
            error_count += 1
    
    print(f"\nOn-demand sync completed:")
    print(f"  Soft-deleted files processed: {len(soft_deleted_files)}")
    print(f"  Files uploaded: {uploaded_count}")
    print(f"  Local files deleted: {deleted_count}")
    print(f"  Database records updated: {updated_count}")
    print(f"  Errors: {error_count}")

def perform_upload_without_deletion_cli(cloud_config, repo_path):
    """Perform upload without deletion for complete sync - keep files in both places"""
    from ui.cloud_sync_dialog import upload_file_to_backup
    from astrofiler_db import fitsFile
    
    # Get bucket info
    bucket_url = cloud_config['bucket_url']
    if bucket_url.startswith('gs://'):
        bucket_name = bucket_url.replace('gs://', '').rstrip('/')
    else:
        bucket_name = bucket_url.rstrip('/')
    
    auth_info = {'auth_string': cloud_config['auth_file_path']}
    
    # Get files without cloud URLs (including soft-deleted and masters)
    fits_files = list(fitsFile.select().where(
        (fitsFile.fitsFileName.is_null(False)) &
        ((fitsFile.fitsFileCloudURL.is_null(True)) | (fitsFile.fitsFileCloudURL == ""))
    ))
    
    print(f"Found {len(fits_files)} files to upload (keeping local copies)")
    
    uploaded_count = 0
    updated_count = 0
    error_count = 0
    
    for i, fits_file in enumerate(fits_files):
        try:
            print(f"[{i+1:3d}/{len(fits_files)}] {os.path.basename(fits_file.fitsFileName)}")
            
            # Get relative path
            full_path = fits_file.fitsFileName
            if full_path.startswith(repo_path):
                relative_path = os.path.relpath(full_path, repo_path)
            else:
                relative_path = os.path.basename(full_path)
            
            # Check if file exists
            if not os.path.exists(full_path):
                logging.warning(f"File not found: {full_path}")
                error_count += 1
                continue
            
            # Upload
            success, cloud_url, message = upload_file_to_backup(
                bucket_name, auth_info, full_path, relative_path
            )
            
            if success:
                fits_file.fitsFileCloudURL = cloud_url
                fits_file.save()
                updated_count += 1
                
                # Check if we actually uploaded (vs already existed)
                if "uploaded" in message.lower():
                    uploaded_count += 1
                
                # Complete Sync: NO deletion - keep files in both places
                if "uploaded" in message.lower():
                    print(f"    → Uploaded (keeping local copy)")
                else:
                    print(f"    → Already exists")
            else:
                logging.error(f"Failed to upload {relative_path}: {message}")
                error_count += 1
                
        except Exception as e:
            logging.error(f"Error processing {fits_file.fitsFileName}: {e}")
            error_count += 1
    
    print(f"\nUpload phase completed:")
    print(f"  Files processed: {len(fits_files)}")
    print(f"  Files uploaded: {uploaded_count}")
    print(f"  Database records updated: {updated_count}")
    print(f"  Errors: {error_count}")

def perform_complete_sync_cli(cloud_config, repo_path):
    """Perform complete sync from command line"""
    from ui.cloud_sync_dialog import list_gcs_bucket_files, download_file_from_gcs, upload_file_to_backup
    from astrofiler_db import fitsFile
    from astrofiler_file import fitsProcessing
    import configparser
    
    # Read configuration file
    config = configparser.ConfigParser()
    config.read('astrofiler.ini')
    
    # Get bucket info
    bucket_url = cloud_config['bucket_url']
    if bucket_url.startswith('gs://'):
        bucket_name = bucket_url.replace('gs://', '').rstrip('/')
    else:
        bucket_name = bucket_url.rstrip('/')
    
    auth_info = {'auth_string': cloud_config['auth_file_path']}
    
    print("Phase 1: Downloading missing files from cloud...")
    
    # Get cloud files
    cloud_files = list_gcs_bucket_files(bucket_name, auth_info)
    print(f"Found {len(cloud_files)} files in cloud storage")
    
    downloaded_count = 0
    registered_count = 0
    
    for i, cloud_file in enumerate(cloud_files):
        print(f"[{i+1:3d}/{len(cloud_files)}] Checking {cloud_file['name']}")
        
        # Check if file already exists in database (already processed)
        filename_only = os.path.basename(cloud_file['name'])
        cloud_url = f"gs://{bucket_name}/{cloud_file['name']}"
        
        # Check if file is already in database/repository by multiple methods
        existing_file = None
        
        # Method 1: Check by exact filename
        try:
            existing_file = fitsFile.get(fitsFile.fitsFileName == filename_only)
            print(f"    → File already exists in repository (by filename): {filename_only}")
        except fitsFile.DoesNotExist:
            pass
        
        # Method 2: Check by cloud URL (for files downloaded previously)
        if existing_file is None:
            try:
                existing_file = fitsFile.get(fitsFile.fitsFileCloudURL == cloud_url)
                print(f"    → File already exists in repository (by cloud URL): {filename_only}")
            except fitsFile.DoesNotExist:
                pass
        
        # Method 3: Check by timestamp pattern (extract date/time from filename)
        if existing_file is None:
            import re
            # Extract timestamp pattern like "20240116031554" from filename
            timestamp_match = re.search(r'-(\d{14})[s-]', filename_only)
            if timestamp_match:
                timestamp = timestamp_match.group(1)
                try:
                    # Look for any file with this timestamp
                    existing_file = fitsFile.get(fitsFile.fitsFileName.contains(timestamp))
                    print(f"    → File already exists in repository (by timestamp {timestamp}): {filename_only}")
                except fitsFile.DoesNotExist:
                    pass
        
        if existing_file is None:
            try:
                print(f"    → Downloading to incoming folder...")
                
                # Get source folder from configuration
                source_path = config.get('DEFAULT', 'source', fallback='')
                if not source_path:
                    logging.error("Source folder not configured. Cannot download files.")
                    continue
                    
                # Ensure source folder exists
                os.makedirs(source_path, exist_ok=True)
                
                # Download to source folder (incoming)
                incoming_file_path = os.path.join(source_path, os.path.basename(cloud_file['name']))
                
                success, message = download_file_from_gcs(
                    bucket_name, auth_info, cloud_file['name'], incoming_file_path
                )
                
                if success:
                    downloaded_count += 1
                    print(f"    → Downloaded successfully")
                    
                    # Register and move if it's a FITS file
                    if incoming_file_path.lower().endswith(('.fits', '.fit', '.fts')):
                        processor = fitsProcessing()
                        # Split path into directory and filename for registerFitsImage
                        root_dir = os.path.dirname(incoming_file_path)
                        filename = os.path.basename(incoming_file_path)
                        result = processor.registerFitsImage(root_dir, filename, moveFiles=True)
                        if result:  # Success includes both new registrations and duplicates
                            registered_count += 1
                            if result == "DUPLICATE":
                                # File already exists in repository, delete the downloaded copy
                                try:
                                    os.remove(incoming_file_path)
                                    print(f"    → File already exists in repository, deleted incoming copy")
                                except OSError as e:
                                    print(f"    → File exists but failed to delete incoming copy: {e}")
                            else:
                                print(f"    → Registered and moved to repository")
                        else:
                            print(f"    → Downloaded but failed to register")
                    else:
                        print(f"    → Downloaded non-FITS file")
                        
            except Exception as e:
                logging.error(f"Failed to download {cloud_file['name']}: {e}")
    
    print(f"\nPhase 1 completed:")
    print(f"  Files downloaded: {downloaded_count}")
    print(f"  Files registered: {registered_count}")
    
    print("\nPhase 2: Uploading local files without cloud URLs...")
    
    # Perform upload without deletion for complete sync (keep files in both places)
    perform_upload_without_deletion_cli(cloud_config, repo_path)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="AstroFiler Cloud Sync Command Line Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                      help='Enable verbose logging')
    parser.add_argument('-c', '--config', default='astrofiler.ini',
                      help='Path to configuration file (default: astrofiler.ini)')
    parser.add_argument('-p', '--profile', choices=['backup', 'complete', 'ondemand'],
                      help='Override sync profile (backup|complete|ondemand)')
    parser.add_argument('-a', '--analyze', action='store_true',
                      help='Only analyze cloud storage, don\'t sync')
    parser.add_argument('-y', '--yes', action='store_true',
                      help='Skip confirmation prompts (auto-confirm)')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        # Load configuration
        config = load_config(args.config)
        cloud_config = get_cloud_config(config)
        
        # Override sync profile if specified
        if args.profile:
            cloud_config['sync_profile'] = args.profile
        
        # Validate bucket access
        validate_bucket_access(cloud_config)
        
        if args.analyze:
            # Perform analysis only
            perform_analysis(cloud_config)
        else:
            # Perform sync
            perform_sync(cloud_config, cloud_config['sync_profile'], args.yes)
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()