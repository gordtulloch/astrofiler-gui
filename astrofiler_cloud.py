import os
import logging
from pathlib import Path

# Debug flag: if True, only report actions; if False, perform sync
DEBUG = True

logger = logging.getLogger(__name__)

def _get_gcs_client(auth_info):
    """
    Create and return a Google Cloud Storage client.
    
    Args:
        auth_info (dict): Authentication information
        
    Returns:
        storage.Client: Authenticated GCS client
    """
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
        
        if 'auth_string' in auth_info and auth_info['auth_string']:
            # Check if it's a file path to a service account key
            auth_path = auth_info['auth_string']
            if os.path.exists(auth_path) and auth_path.endswith('.json'):
                # Use service account key file
                credentials = service_account.Credentials.from_service_account_file(auth_path)
                client = storage.Client(credentials=credentials)
                logger.info(f"Authenticated using service account key: {auth_path}")
            else:
                # Try default credentials
                client = storage.Client()
                logger.info("Using default Google Cloud credentials")
        else:
            # Use default credentials (ADC, environment, etc.)
            client = storage.Client()
            logger.info("Using default Google Cloud credentials")
            
        return client
        
    except ImportError:
        raise ImportError("Google Cloud Storage library not installed. Run: pip install google-cloud-storage")
    except Exception as e:
        raise Exception(f"Failed to authenticate with Google Cloud: {e}")

def _parse_gcs_path(gcs_path):
    """
    Parse GCS path into bucket name and prefix.
    
    Args:
        gcs_path (str): GCS path like gs://bucket-name/path/
        
    Returns:
        tuple: (bucket_name, prefix)
    """
    if not gcs_path.startswith('gs://'):
        raise ValueError("GCS path must start with gs://")
    
    path_parts = gcs_path[5:].split('/', 1)  # Remove gs:// and split
    bucket_name = path_parts[0]
    prefix = path_parts[1] if len(path_parts) > 1 else ''
    
    # Ensure prefix ends with / if not empty
    if prefix and not prefix.endswith('/'):
        prefix += '/'
        
    return bucket_name, prefix

def _upload_file_to_gcs(client, bucket_name, local_file_path, gcs_object_name):
    """
    Upload a file to Google Cloud Storage, preserving the local directory structure.
    
    Args:
        client: GCS client
        bucket_name (str): Name of the GCS bucket
        local_file_path (str): Full path to local file
        gcs_object_name (str): Object name in GCS (includes directory structure)
    """
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_object_name)
        
        blob.upload_from_filename(local_file_path)
        logger.debug(f"Successfully uploaded: {local_file_path} -> gs://{bucket_name}/{gcs_object_name}")
        
    except Exception as e:
        logger.error(f"Failed to upload {local_file_path}: {e}")
        raise

def _download_file_from_gcs(client, bucket_name, gcs_object_name, local_file_path):
    """
    Download a file from Google Cloud Storage, preserving the directory structure.
    
    Args:
        client: GCS client
        bucket_name (str): Name of the GCS bucket
        gcs_object_name (str): Object name in GCS (includes directory structure)
        local_file_path (str): Full path where to save the file locally
    """
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_object_name)
        
        # Create directory structure if it doesn't exist
        local_dir = os.path.dirname(local_file_path)
        if local_dir:
            os.makedirs(local_dir, exist_ok=True)
        
        blob.download_to_filename(local_file_path)
        logger.debug(f"Successfully downloaded: gs://{bucket_name}/{gcs_object_name} -> {local_file_path}")
        
    except Exception as e:
        logger.error(f"Failed to download gs://{bucket_name}/{gcs_object_name}: {e}")
        raise

def _should_download_file(blob, local_file_path):
    """
    Determine if a file should be downloaded from GCS.
    
    Args:
        blob: GCS blob object
        local_file_path (str): Path to local file
        
    Returns:
        tuple: (should_download: bool, reason: str)
    """
    if not os.path.exists(local_file_path):
        return True, "file does not exist locally"
    
    # Compare file sizes
    local_size = os.path.getsize(local_file_path)
    gcs_size = blob.size
    
    if local_size != gcs_size:
        return True, f"size mismatch (local: {local_size}, GCS: {gcs_size})"
    
    # Compare modification times
    local_mtime = os.path.getmtime(local_file_path)
    gcs_mtime = blob.time_created.timestamp() if blob.time_created else 0
    
    # Allow some tolerance for timestamp differences (1 second)
    if abs(local_mtime - gcs_mtime) > 1:
        return True, f"timestamp mismatch (local: {local_mtime}, GCS: {gcs_mtime})"
    
    return False, "file is up to date"

def _register_fits_file(file_path):
    """
    Register a FITS file in the database using the single file registry.
    
    Args:
        file_path (str): Path to the FITS file
    """
    try:
        # Import here to avoid circular imports
        from astrofiler_file import registerFitsImage
        
        if file_path.lower().endswith(('.fits', '.fit', '.fts')):
            success = registerFitsImage(file_path, moveFiles=False)
            if success:
                logger.info(f"Registered FITS file in database: {file_path}")
            else:
                logger.warning(f"Failed to register FITS file: {file_path}")
        else:
            logger.debug(f"Skipped non-FITS file: {file_path}")
            
    except Exception as e:
        logger.error(f"Error registering FITS file {file_path}: {e}")

def sync_with_google_cloud_repo(gcs_repo_path, auth_info, local_repo_path, sync_to_local=False, debug=DEBUG, progress_callback=None):
    """
    Connects to a Google Cloud Repository and synchronizes files with the local repository.
    If debug is True, only reports actions; if False, performs actual sync.
    
    Args:
        gcs_repo_path (str): Path to the Google Cloud Repository (gs://bucket/path).
        auth_info (dict): Authentication information for Google Cloud.
        local_repo_path (str): Path to the local repository directory.
        sync_to_local (bool): If True, download missing files from GCS to local repo.
        debug (bool): If True, only report actions.
        progress_callback (callable): Optional callback function for progress updates.
                                     Called with (current_count, total_count, operation_type, filename)
    """
    logger.info(f"Google Cloud Sync - Debug mode: {debug}")
    logger.info(f"GCS repository path: {gcs_repo_path}")
    logger.info(f"Local repository path: {local_repo_path}")
    logger.info(f"Sync to local enabled: {sync_to_local}")
    logger.info(f"Authentication info provided: {bool(auth_info)}")
    
    if not gcs_repo_path:
        logger.warning("No Google Cloud repository path specified in configuration")
        return
    
    if not local_repo_path:
        logger.warning("No local repository path specified in configuration")
        return
    
    if not os.path.exists(local_repo_path):
        logger.warning(f"Local repository path does not exist: {local_repo_path}")
        return
    
        # Find all files in the local repository
    local_files = []
    for root, dirs, files in os.walk(local_repo_path):
        # Skip hidden directories and __pycache__
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for file in files:
            if not file.startswith('.') and not file.endswith('.pyc'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, local_repo_path)
                local_files.append(relative_path)
    
    total_local_files = len(local_files)
    logger.info(f"Found {total_local_files} local files to potentially sync")
    
    # Initialize progress
    if progress_callback:
        progress_callback(0, total_local_files, "scan", "Completed local file scan")
        
    try:
        # Initialize GCS client (in both debug and live modes)
        client = _get_gcs_client(auth_info)
        bucket_name, prefix = _parse_gcs_path(gcs_repo_path)
        
        logger.info(f"Connected to GCS bucket: {bucket_name} with prefix: {prefix}")
        
        # Update progress with connection info
        if progress_callback:
            progress_callback(5, 100, "connect", f"Connected to GCS bucket: {bucket_name}")
        
        # Upload local files to GCS
        if debug:
            logger.info("DEBUG MODE: Starting UPLOAD analysis:")
        else:
            logger.info("LIVE MODE: Starting UPLOAD operations:")
            
        upload_count = 0
        for i, file_path in enumerate(local_files):
            try:
                full_local_path = os.path.join(local_repo_path, file_path)
                # Preserve the complete local directory structure in GCS
                # Convert backslashes to forward slashes for GCS compatibility
                gcs_object_name = prefix + file_path.replace('\\', '/')
                
                # Update progress
                if progress_callback:
                    continue_operation = progress_callback(i, total_local_files, "upload", f"Processing {file_path}")
                    # If the callback returns False, it means the operation was cancelled
                    if continue_operation is False:
                        logger.info("Google Sync operation was cancelled by user")
                        return
                
                if debug:
                    logger.info(f"[DEBUG] Would upload: {file_path} -> gs://{bucket_name}/{gcs_object_name}")
                else:
                    logger.info(f"Uploading: {file_path} -> gs://{bucket_name}/{gcs_object_name}")
                    _upload_file_to_gcs(client, bucket_name, full_local_path, gcs_object_name)
                    
                upload_count += 1
                
            except Exception as e:
                logger.error(f"Failed to upload {file_path}: {e}")
        
        if debug:
            logger.info(f"DEBUG MODE: Would upload {upload_count} files to GCS")
        else:
            logger.info(f"Uploaded {upload_count} files to GCS")
            
        
        # Download missing files from GCS if enabled
        if sync_to_local:
            if debug:
                logger.info("DEBUG MODE: Starting DOWNLOAD analysis:")
            else:
                logger.info("LIVE MODE: Starting DOWNLOAD operations:")
                
            download_count = 0
            skip_count = 0
            
            try:
                bucket = client.bucket(bucket_name)
                
                # List all objects in the bucket with the specified prefix
                blobs = list(bucket.list_blobs(prefix=prefix))
                total_gcs_files = len(blobs)
                
                if progress_callback:
                    progress_callback(0, total_gcs_files, "download_prepare", "Starting download operations")
                
                for i, blob in enumerate(blobs):
                    # Calculate relative path by removing prefix
                    if blob.name.startswith(prefix):
                        relative_path = blob.name[len(prefix):]
                        
                        # Skip if it's just the prefix (directory marker)
                        if not relative_path:
                            continue
                            
                        # Preserve directory structure when creating local path
                        local_file_path = os.path.join(local_repo_path, relative_path.replace('/', os.path.sep))
                        
                        # Check if file should be downloaded
                        should_download, reason = _should_download_file(blob, local_file_path)
                        
                        if should_download:
                            try:
                                # Update progress callback
                                if progress_callback:
                                    continue_operation = progress_callback(i, total_gcs_files, "download", f"Processing {relative_path}")
                                    # If the callback returns False, it means the operation was cancelled
                                    if continue_operation is False:
                                        logger.info("Google Sync download operation was cancelled by user")
                                        return
                                    
                                if debug:
                                    logger.info(f"[DEBUG] Would download: gs://{bucket_name}/{blob.name} -> {relative_path} (reason: {reason})")
                                else:
                                    logger.info(f"Downloading: gs://{bucket_name}/{blob.name} -> {relative_path} (reason: {reason})")
                                    _download_file_from_gcs(client, bucket_name, blob.name, local_file_path)
                                    
                                    # Register FITS files in database
                                    _register_fits_file(local_file_path)
                                
                                download_count += 1
                                
                            except Exception as e:
                                logger.error(f"Failed to download {blob.name}: {e}")
                        else:
                            logger.debug(f"Skipping: {relative_path} ({reason})")
                            skip_count += 1
                
                if debug:
                    logger.info(f"DEBUG MODE: Would download {download_count} files from GCS, would skip {skip_count} up-to-date files")
                else:
                    logger.info(f"Downloaded {download_count} files from GCS, skipped {skip_count} up-to-date files")
                
            except Exception as e:
                logger.error(f"Failed to list/download files from GCS: {e}")
        
        if debug:
            logger.info("DEBUG MODE: Synchronization analysis completed successfully")
        else:
            logger.info("Synchronization completed successfully")
            
        # Final progress update
        if progress_callback:
            try:
                progress_callback(100, 100, "complete", "Synchronization completed successfully")
            except Exception as e:
                logger.error(f"Error in final progress callback: {e}")
                # Don't raise here as the sync was successful
            
    except ImportError as e:
        logger.error(f"Google Cloud Storage library not available: {e}")
        logger.info("To install: pip install google-cloud-storage")
        # Report error in progress callback if available
        if progress_callback:
            progress_callback(0, 100, "error", f"Missing Google Cloud Storage library: {e}")
        raise
        
    except Exception as e:
        import traceback
        logger.error(f"Synchronization failed: {e}")
        logger.error(traceback.format_exc())
        # Report error in progress callback if available
        if progress_callback:
            progress_callback(0, 100, "error", f"Sync error: {e}")
        raise

def validate_google_cloud_config(repo_path, auth_info):
    """
    Validates the Google Cloud configuration.
    
    Args:
        repo_path (str): Path to the Google Cloud Repository.
        auth_info (dict): Authentication information for Google Cloud.
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not repo_path:
        return False, "Repository path is required"
    
    if not isinstance(repo_path, str) or not repo_path.strip():
        return False, "Repository path must be a non-empty string"
    
    if not auth_info:
        return False, "Authentication information is required"
    
    # Basic validation of auth_info structure
    if not isinstance(auth_info, dict):
        return False, "Authentication information must be a dictionary"
    
    # Could add more specific validation based on Google Cloud auth requirements
    
    return True, "Configuration is valid"
