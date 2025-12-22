"""
Google Drive Integration Service
Manages database storage in Google Drive
"""
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io
import os
import json
import logging
from typing import Optional, Dict, List
from app.config import settings

logger = logging.getLogger(__name__)

class GoogleDriveManager:
    """Manages Google Drive operations for database storage"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    def __init__(self):
        self.service = None
        self.folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
        self.credentials_file = settings.GOOGLE_CREDENTIALS_FILE
        self.token_file = settings.GOOGLE_TOKEN_FILE
        self._pending_flow = None  # Store flow for callback handling
        self._flow_state_file = os.path.join(os.path.dirname(self.token_file), "oauth_flow_state.json")  # Store flow state
        
        # Check for credentials in environment variable first (for Render persistence)
        if os.getenv("GOOGLE_CREDENTIALS_JSON"):
            logger.info("📥 Found Google credentials in environment variable")
            try:
                os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
                with open(self.credentials_file, 'w') as f:
                    f.write(os.getenv("GOOGLE_CREDENTIALS_JSON"))
                logger.info(f"✅ Wrote credentials from environment variable to {self.credentials_file}")
            except Exception as e:
                logger.error(f"❌ Error writing credentials from env var: {e}")
        
        # Check for token in environment variable (for Render persistence)
        if os.getenv("GOOGLE_TOKEN_JSON"):
            logger.info("📥 Found Google token in environment variable")
            try:
                os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
                with open(self.token_file, 'w') as f:
                    f.write(os.getenv("GOOGLE_TOKEN_JSON"))
                logger.info(f"✅ Wrote token from environment variable to {self.token_file}")
            except Exception as e:
                logger.error(f"❌ Error writing token from env var: {e}")
        
        # Don't authenticate immediately - let it fail gracefully if no token
        # Only authenticate if credentials file exists
        if os.path.exists(self.credentials_file):
            try:
                self._authenticate()
            except Exception as e:
                logger.warning(f"Initial authentication deferred: {e}")
                # Will authenticate when needed or via callback
        else:
            logger.info("Google credentials file not found - Google Drive features will be disabled until configured")
            logger.info("💡 Tip: Upload credentials via Admin panel or set GOOGLE_CREDENTIALS_JSON environment variable")
    
    def _authenticate(self):
        """Authenticate with Google Drive API"""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
                logger.info(f"✅ Token file loaded from: {self.token_file}")
            except Exception as e:
                logger.warning(f"⚠️ Error loading token: {e}")
                creds = None
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("🔄 Token expired, refreshing...")
                    creds.refresh(Request())
                    # Save refreshed token
                    with open(self.token_file, 'w') as token:
                        token.write(creds.to_json())
                    logger.info("✅ Token refreshed successfully")
                except Exception as e:
                    logger.error(f"❌ Error refreshing token: {e}")
                    logger.warning("⚠️ Token refresh failed - authorization may be required")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.credentials_file):
                    logger.warning(f"⚠️ Google credentials file not found: {self.credentials_file}")
                    logger.info("ℹ️ Google Drive features will be disabled until configured")
                    return  # Don't raise exception - allow app to start
                
                # For web application, use callback flow
                # Don't block here - return None and let callback route handle it
                logger.warning("⚠️ Google Drive authorization required. Use /api/admin/drive/authorize endpoint to get authorization URL")
                return  # Don't raise exception - allow app to start
            
            # Save credentials
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        if creds:
            try:
                self.service = build('drive', 'v3', credentials=creds)
                logger.info("✅ Google Drive authenticated successfully")
            except Exception as e:
                logger.error(f"❌ Error building Drive service: {e}")
                self.service = None
        else:
            logger.warning("⚠️ Google Drive not authenticated - app will continue without Drive features")
    
    def ensure_folder_exists(self) -> str:
        """Ensure the database folder exists in Drive"""
        if not self.service:
            raise Exception("Google Drive not authenticated. Please authorize first.")
        
        if self.folder_id:
            try:
                self.service.files().get(fileId=self.folder_id).execute()
                logger.info(f"✅ Using existing folder: {self.folder_id}")
                return self.folder_id
            except HttpError:
                logger.info("Folder not found, creating new one...")
        
        # Create folder
        folder_metadata = {
            'name': 'PharmaStock_Database',
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = self.service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        
        self.folder_id = folder.get('id')
        logger.info(f"✅ Created folder: {self.folder_id}")
        return self.folder_id
    
    def download_database(self, local_path: str) -> bool:
        """Download database from Google Drive"""
        if not self.service:
            logger.error("Google Drive not authenticated")
            return False
        
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Ensure folder exists first
            if not self.folder_id:
                self.folder_id = self.ensure_folder_exists()
            
            # Find database file in folder first
            query = f"name='{settings.DB_FILENAME}' and '{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            # If not found in app folder, search Drive-wide (fallback)
            if not items:
                logger.info(f"Database not found in folder '{self.folder_id}', searching Drive-wide...")
                
                # First, try searching for database file directly
                query_wide = f"name='{settings.DB_FILENAME}' and trashed=false"
                results_wide = self.service.files().list(q=query_wide, orderBy='modifiedTime desc', pageSize=10).execute()
                items_wide = results_wide.get('files', [])
                
                # If still not found, search inside PharmaStock_Database folders
                if not items_wide:
                    logger.info("Searching inside PharmaStock_Database folders...")
                    # Find all PharmaStock_Database folders
                    folder_query = "name='PharmaStock_Database' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                    folder_results = self.service.files().list(q=folder_query, fields='files(id,name)').execute()
                    folders = folder_results.get('files', [])
                    
                    logger.info(f"Found {len(folders)} PharmaStock_Database folder(s), searching inside them...")
                    
                    # Search for database file inside each folder
                    all_found_files = []
                    for folder in folders:
                        folder_id = folder['id']
                        folder_name = folder.get('name', 'Unknown')
                        logger.info(f"  🔍 Searching inside folder '{folder_name}' (ID: {folder_id})...")
                        
                        # List ALL files in folder first to see what's actually there
                        try:
                            all_files_query = f"'{folder_id}' in parents and trashed=false"
                            all_files_results = self.service.files().list(
                                q=all_files_query, 
                                fields='files(id,name,mimeType,size,modifiedTime)',
                                pageSize=100
                            ).execute()
                            all_files = all_files_results.get('files', [])
                            logger.info(f"  📁 Total files in folder '{folder_name}': {len(all_files)}")
                            
                            # Log ALL files in the folder
                            for f in all_files:
                                file_name = f.get('name', 'Unknown')
                                file_type = f.get('mimeType', 'unknown')
                                file_size = f.get('size', 0)
                                logger.info(f"    📄 {file_name} (Type: {file_type}, Size: {int(file_size)/(1024*1024):.2f} MB if size>0)")
                                
                                # Check if this file matches our database filename (exact or partial)
                                if settings.DB_FILENAME.lower() in file_name.lower() or file_name.lower().endswith('.db'):
                                    logger.info(f"      ⭐ This file matches database pattern!")
                                    all_found_files.append(f)
                            
                            # Also try exact match query
                            file_query = f"name='{settings.DB_FILENAME}' and '{folder_id}' in parents and trashed=false"
                            file_results = self.service.files().list(q=file_query, orderBy='modifiedTime desc', pageSize=10).execute()
                            exact_matches = file_results.get('files', [])
                            
                            if exact_matches:
                                logger.info(f"  ✅ Found {len(exact_matches)} exact match(es) for '{settings.DB_FILENAME}' in folder '{folder_name}'")
                                all_found_files.extend(exact_matches)
                                
                        except Exception as e:
                            logger.error(f"  ❌ Error searching folder '{folder_name}': {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                    
                    # Use the most recently modified file if we found any
                    if all_found_files:
                        # Remove duplicates by ID
                        unique_files = {}
                        for f in all_found_files:
                            file_id = f.get('id')
                            if file_id not in unique_files:
                                unique_files[file_id] = f
                            else:
                                # Keep the one with more info
                                if f.get('size') and not unique_files[file_id].get('size'):
                                    unique_files[file_id] = f
                        
                        # Sort by modifiedTime (newest first)
                        sorted_files = sorted(
                            unique_files.values(), 
                            key=lambda x: x.get('modifiedTime', ''), 
                            reverse=True
                        )
                        items_wide = sorted_files[:1]  # Take the newest one
                        logger.info(f"✅ Found {len(unique_files)} unique database file(s) across all folders, using newest: {items_wide[0].get('name')}")
                    else:
                        logger.warning(f"⚠️ No database files found in any of the {len(folders)} PharmaStock_Database folders")
                
                if items_wide:
                    logger.info(f"✅ Found database in Drive, downloading...")
                    items = items_wide  # Use the found file
                else:
                    logger.warning(f"Database '{settings.DB_FILENAME}' not found anywhere in Drive")
                    logger.info("💡 Tip: Use 'Upload to Drive' to upload your local database first, or use 'Refresh Now' to fetch data and create a database")
                    return False
            
            file_id = items[0]['id']
            
            # Download file
            request = self.service.files().get_media(fileId=file_id)
            fh = io.FileIO(local_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(f"Download progress: {int(status.progress() * 100)}%")
            
            logger.info(f"✅ Downloaded database: {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error downloading database: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def get_drive_database_timestamp(self) -> Optional[str]:
        """Get the modified timestamp of the database file in Google Drive"""
        if not self.service:
            return None
        
        try:
            if not self.folder_id:
                self.folder_id = self.ensure_folder_exists()
            
            query = f"name='{settings.DB_FILENAME}' and '{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            # If not found in app folder, search inside PharmaStock_Database folders
            if not items:
                logger.info("Searching inside PharmaStock_Database folders for timestamp...")
                folder_query = "name='PharmaStock_Database' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                folder_results = self.service.files().list(q=folder_query, fields='files(id,name)').execute()
                folders = folder_results.get('files', [])
                
                logger.info(f"Found {len(folders)} PharmaStock_Database folder(s) for timestamp search...")
                for folder in folders:
                    folder_id = folder['id']
                    folder_name = folder.get('name', 'Unknown')
                    file_query = f"name='{settings.DB_FILENAME}' and '{folder_id}' in parents and trashed=false"
                    try:
                        file_results = self.service.files().list(q=file_query, orderBy='modifiedTime desc', pageSize=1).execute()
                        folder_files = file_results.get('files', [])
                        if folder_files:
                            logger.info(f"✅ Found database in folder '{folder_name}' for timestamp")
                            items = folder_files
                            break
                    except Exception as e:
                        logger.error(f"Error searching folder '{folder_name}' for timestamp: {e}")
            
            if items:
                file_id = items[0]['id']
                file_info = self.service.files().get(
                    fileId=file_id,
                    fields='modifiedTime'
                ).execute()
                return file_info.get('modifiedTime')
            return None
        except Exception as e:
            logger.warning(f"⚠️ Error getting Drive timestamp: {e}")
            return None
    
    def upload_database(self, local_path: str, check_conflicts: bool = True) -> bool:
        """Upload database to Google Drive (with versioning and progress tracking for large files)"""
        if not self.service:
            logger.error("Google Drive not authenticated")
            return False
        
        try:
            if not os.path.exists(local_path):
                logger.error(f"Database file not found: {local_path}")
                return False
            
            file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
            logger.info(f"📤 Starting upload: {file_size_mb:.2f} MB")
            
            # Conflict resolution: Check if Drive database is newer
            if check_conflicts:
                drive_timestamp = self.get_drive_database_timestamp()
                if drive_timestamp:
                    from datetime import datetime
                    local_mtime = datetime.fromtimestamp(os.path.getmtime(local_path))
                    drive_mtime = datetime.fromisoformat(drive_timestamp.replace('Z', '+00:00'))
                    
                    # Compare timestamps (accounting for timezone)
                    if drive_mtime > local_mtime:
                        logger.warning(f"⚠️ Drive database is newer (Drive: {drive_timestamp}, Local: {local_mtime.isoformat()})")
                        logger.info("📥 Downloading Drive database first to merge changes...")
                        # Download Drive version first
                        temp_path = local_path + '.drive_backup'
                        if self.download_database(temp_path):
                            logger.info("✅ Downloaded Drive version. Uploading local changes will merge with Drive version.")
                            # Note: The document_tracker will prevent duplicates when merging
                        else:
                            logger.warning("⚠️ Could not download Drive version, proceeding with upload anyway")
            
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Ensure folder exists first
            if not self.folder_id:
                self.folder_id = self.ensure_folder_exists()
            
            # Find existing file
            query = f"name='{settings.DB_FILENAME}' and '{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            file_metadata: dict = {'name': settings.DB_FILENAME}
            # Use resumable upload for files > 5MB, with chunk size for large files
            chunk_size = 10 * 1024 * 1024  # 10MB chunks for large files
            if file_size_mb > 5:
                media = MediaFileUpload(local_path, resumable=True, chunksize=chunk_size)
                logger.info(f"📤 Using resumable upload with {chunk_size / (1024*1024):.0f}MB chunks")
            else:
                media = MediaFileUpload(local_path, resumable=False)
            
            if items:
                # Update existing file
                file_id = items[0]['id']
                logger.info(f"📤 Updating existing file: {file_id}")
                
                request = self.service.files().update(
                    fileId=file_id,
                    body=file_metadata,
                    media_body=media
                )
                
                if file_size_mb > 5:
                    # Use resumable upload with progress tracking
                    response = None
                    while response is None:
                        status, response = request.next_chunk()
                        if status:
                            progress = int(status.progress() * 100)
                            logger.info(f"📤 Upload progress: {progress}%")
                    logger.info(f"✅ Updated database in Drive: {response.get('id')}")
                else:
                    # Small file, direct upload
                    file = request.execute()
                    logger.info(f"✅ Updated database in Drive: {file.get('id')}")
            else:
                # Create new file
                file_metadata['parents'] = [self.folder_id]  # type: ignore
                logger.info(f"📤 Creating new file in folder: {self.folder_id}")
                
                request = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                )
                
                if file_size_mb > 5:
                    # Use resumable upload with progress tracking
                    response = None
                    while response is None:
                        status, response = request.next_chunk()
                        if status:
                            progress = int(status.progress() * 100)
                            logger.info(f"📤 Upload progress: {progress}%")
                    logger.info(f"✅ Uploaded database to Drive: {response.get('id')}")
                else:
                    # Small file, direct upload
                    file = request.execute()
                    logger.info(f"✅ Uploaded database to Drive: {file.get('id')}")
            
            logger.info(f"✅ Upload complete: {file_size_mb:.2f} MB")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error uploading database: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def get_database_info(self) -> Dict:
        """Get database file info (size, modified time)"""
        # Check authentication and try to re-authenticate if needed
        if not self.is_authenticated():
            return {'exists': False, 'error': 'Not authenticated', 'message': 'Google Drive not authenticated. Please authorize first.'}
        
        try:
            # First, try to find database in the app's specific folder
            if not self.folder_id:
                self.folder_id = self.ensure_folder_exists()
            
            query = f"name='{settings.DB_FILENAME}' and '{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            # If not found in specific folder, search Drive-wide (fallback)
            if not items:
                logger.info(f"Database not found in folder '{self.folder_id}', searching Drive-wide...")
                
                # First, try searching for database file directly
                query_wide = f"name='{settings.DB_FILENAME}' and trashed=false"
                results_wide = self.service.files().list(q=query_wide, orderBy='modifiedTime desc', pageSize=10).execute()
                items_wide = results_wide.get('files', [])
                
                # If still not found, search inside PharmaStock_Database folders
                if not items_wide:
                    logger.info("Searching inside PharmaStock_Database folders...")
                    # Find all PharmaStock_Database folders
                    folder_query = "name='PharmaStock_Database' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                    folder_results = self.service.files().list(q=folder_query, fields='files(id,name)').execute()
                    folders = folder_results.get('files', [])
                    
                    logger.info(f"Found {len(folders)} PharmaStock_Database folder(s), searching inside them...")
                    
                    # Search for database file inside each folder (newest first)
                    all_found_files = []
                    for folder in folders:
                        folder_id = folder['id']
                        file_query = f"name='{settings.DB_FILENAME}' and '{folder_id}' in parents and trashed=false"
                        file_results = self.service.files().list(q=file_query, orderBy='modifiedTime desc', pageSize=1).execute()
                        folder_files = file_results.get('files', [])
                        if folder_files:
                            all_found_files.extend(folder_files)
                    
                    # Use the most recently modified file
                    if all_found_files:
                        # Sort by modifiedTime (newest first)
                        items_wide = sorted(all_found_files, key=lambda x: x.get('modifiedTime', ''), reverse=True)[:1]
                        logger.info(f"✅ Found {len(all_found_files)} database file(s) inside PharmaStock_Database folders")
                
                if items_wide:
                    # Found database elsewhere in Drive
                    logger.info(f"✅ Found database in Drive (not in app folder): {items_wide[0].get('name')}")
                    file_id = items_wide[0]['id']
                    file_info = self.service.files().get(
                        fileId=file_id,
                        fields='id,name,size,modifiedTime,parents'
                    ).execute()
                    
                    # Get parent folder name for display
                    parent_folders = []
                    if file_info.get('parents'):
                        for parent_id in file_info.get('parents', []):
                            try:
                                parent_info = self.service.files().get(fileId=parent_id, fields='name').execute()
                                parent_folders.append(parent_info.get('name', 'Unknown'))
                            except:
                                pass
                    
                    return {
                        'exists': True,
                        'size': int(file_info.get('size', 0)),
                        'size_mb': round(int(file_info.get('size', 0)) / (1024 * 1024), 2),
                        'modified': file_info.get('modifiedTime'),
                        'id': file_id,
                        'folder_id': self.folder_id,
                        'location': ', '.join(parent_folders) if parent_folders else 'My Drive',
                        'note': f'Found in: {", ".join(parent_folders) if parent_folders else "My Drive"} (not in app folder)'
                    }
            
            # Found in app folder
            if items:
                file_id = items[0]['id']
                file_info = self.service.files().get(
                    fileId=file_id,
                    fields='id,name,size,modifiedTime'
                ).execute()
                return {
                    'exists': True,
                    'size': int(file_info.get('size', 0)),
                    'size_mb': round(int(file_info.get('size', 0)) / (1024 * 1024), 2),
                    'modified': file_info.get('modifiedTime'),
                    'id': file_id,
                    'folder_id': self.folder_id,
                    'location': 'App Folder'
                }
            
            return {
                'exists': False,
                'message': f'Database not found in Google Drive folder. Upload it first using the refresh function.',
                'folder_id': self.folder_id
            }
        except Exception as e:
            logger.error(f"Error getting database info: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'exists': False,
                'error': str(e),
                'message': f'Error checking database: {str(e)}'
            }
    
    def list_all_database_files(self) -> List[Dict]:
        """List all database files in Google Drive, sorted by modification time (newest first)"""
        if not self.is_authenticated():
            return []
        
        try:
            files = []
            
            # First, search for database files directly (not in folders)
            query = f"name='{settings.DB_FILENAME}' and trashed=false"
            results = self.service.files().list(
                q=query,
                orderBy='modifiedTime desc',
                fields='files(id,name,size,modifiedTime,createdTime,parents)'
            ).execute()
            
            for file_info in results.get('files', []):
                # Get parent folder names
                parent_folders = []
                if file_info.get('parents'):
                    for parent_id in file_info.get('parents', []):
                        try:
                            parent_info = self.service.files().get(fileId=parent_id, fields='name').execute()
                            parent_folders.append(parent_info.get('name', 'Unknown'))
                        except:
                            parent_folders.append('Unknown')
                
                files.append({
                    'id': file_info.get('id'),
                    'name': file_info.get('name'),
                    'size': int(file_info.get('size', 0)),
                    'size_mb': round(int(file_info.get('size', 0)) / (1024 * 1024), 2),
                    'modified': file_info.get('modifiedTime'),
                    'created': file_info.get('createdTime'),
                    'location': ', '.join(parent_folders) if parent_folders else 'My Drive',
                    'parent_ids': file_info.get('parents', [])
                })
            
            # Also search inside PharmaStock_Database folders
            logger.info("Searching inside PharmaStock_Database folders...")
            folder_query = "name='PharmaStock_Database' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            folder_results = self.service.files().list(q=folder_query, fields='files(id,name)').execute()
            folders = folder_results.get('files', [])
            
            logger.info(f"Found {len(folders)} PharmaStock_Database folder(s)")
            
            for folder in folders:
                folder_id = folder['id']
                file_query = f"name='{settings.DB_FILENAME}' and '{folder_id}' in parents and trashed=false"
                file_results = self.service.files().list(
                    q=file_query,
                    orderBy='modifiedTime desc',
                    fields='files(id,name,size,modifiedTime,createdTime,parents)'
                ).execute()
                
                for file_info in file_results.get('files', []):
                    # Check if we already have this file (avoid duplicates)
                    if not any(f['id'] == file_info.get('id') for f in files):
                        parent_folders = [folder.get('name', 'PharmaStock_Database')]
                        files.append({
                            'id': file_info.get('id'),
                            'name': file_info.get('name'),
                            'size': int(file_info.get('size', 0)),
                            'size_mb': round(int(file_info.get('size', 0)) / (1024 * 1024), 2),
                            'modified': file_info.get('modifiedTime'),
                            'created': file_info.get('createdTime'),
                            'location': ', '.join(parent_folders) if parent_folders else 'My Drive',
                            'parent_ids': file_info.get('parents', [])
                        })
            
            # Sort all files by modifiedTime (newest first)
            files.sort(key=lambda x: x.get('modified', ''), reverse=True)
            
            logger.info(f"Found {len(files)} total database file(s)")
            return files
        except Exception as e:
            logger.error(f"Error listing database files: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def delete_database_file(self, file_id: str) -> bool:
        """Delete a database file from Google Drive"""
        if not self.is_authenticated():
            logger.error("Google Drive not authenticated")
            return False
        
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"✅ Deleted database file: {file_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting database file {file_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def cleanup_old_database_files(self, keep_count: int = 2) -> Dict:
        """Delete old database files, keeping only the most recent N files"""
        if not self.is_authenticated():
            return {'success': False, 'message': 'Google Drive not authenticated'}
        
        try:
            all_files = self.list_all_database_files()
            
            if len(all_files) <= keep_count:
                return {
                    'success': True,
                    'message': f'Only {len(all_files)} file(s) found, keeping all (limit: {keep_count})',
                    'deleted': [],
                    'kept': [f['id'] for f in all_files]
                }
            
            # Sort by modified time (newest first) - already sorted by API, but ensure it
            all_files.sort(key=lambda x: x.get('modified', ''), reverse=True)
            
            # Keep the most recent N files
            files_to_keep = all_files[:keep_count]
            files_to_delete = all_files[keep_count:]
            
            deleted = []
            failed = []
            
            for file_info in files_to_delete:
                file_id = file_info['id']
                if self.delete_database_file(file_id):
                    deleted.append({
                        'id': file_id,
                        'location': file_info['location'],
                        'modified': file_info['modified']
                    })
                else:
                    failed.append({
                        'id': file_id,
                        'location': file_info['location']
                    })
            
            return {
                'success': True,
                'message': f'Cleaned up {len(deleted)} old database file(s), kept {len(files_to_keep)} most recent',
                'deleted': deleted,
                'kept': [f['id'] for f in files_to_keep],
                'failed': failed
            }
        except Exception as e:
            logger.error(f"Error cleaning up old database files: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Error cleaning up files: {str(e)}'
            }
    
    def is_authenticated(self) -> bool:
        """Check if Google Drive is authenticated"""
        # If service is None, try to authenticate again (in case token was just saved)
        if self.service is None:
            if os.path.exists(self.token_file):
                try:
                    logger.info("🔄 Service is None but token exists, attempting re-authentication...")
                    self._authenticate()
                    if self.service is not None:
                        logger.info("✅ Re-authentication successful")
                    else:
                        logger.warning("⚠️ Re-authentication completed but service is still None")
                except Exception as e:
                    logger.error(f"❌ Failed to re-authenticate: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        return self.service is not None
    
    def get_authorization_url(self) -> str:
        """Get Google Drive OAuth authorization URL"""
        if not os.path.exists(self.credentials_file):
            # Check if credentials are provided via environment variable
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                try:
                    # Write credentials from environment variable to file
                    os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
                    with open(self.credentials_file, 'w') as f:
                        f.write(creds_json)
                    logger.info(f"✅ Created credentials file from environment variable")
                except Exception as e:
                    logger.error(f"❌ Error writing credentials from environment: {e}")
                    raise FileNotFoundError(f"Google credentials file not found and failed to create from environment: {self.credentials_file}")
            else:
                raise FileNotFoundError(
                    f"Google credentials file not found: {self.credentials_file}\n"
                    f"Please upload google_credentials.json via the admin panel or set GOOGLE_CREDENTIALS_JSON environment variable."
                )
        
        redirect_uri = settings.GOOGLE_OAUTH_CALLBACK_URL
        logger.info(f"🔵 Using redirect URI: {redirect_uri}")
        logger.info(f"🔵 Credentials file: {self.credentials_file} (exists: {os.path.exists(self.credentials_file)})")
        
        # Create OAuth flow
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=self.SCOPES,
            redirect_uri=redirect_uri
        )
        
        # Verify redirect_uri is set correctly on the flow
        logger.info(f"🔵 Flow redirect_uri: {flow.redirect_uri}")
        
        # Store flow state for callback (persist across requests)
        flow_state = {
            'redirect_uri': redirect_uri,
            'scopes': self.SCOPES
        }
        os.makedirs(os.path.dirname(self._flow_state_file), exist_ok=True)
        with open(self._flow_state_file, 'w') as f:
            json.dump(flow_state, f)
        
        # Store flow for callback (in-memory backup)
        self._pending_flow = flow
        
        # Get authorization URL
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent to get refresh token
        )
        
        # Log the full authorization URL to check redirect_uri parameter
        logger.info(f"🔵 Full authorization URL: {authorization_url}")
        logger.info(f"🔵 State: {state}")
        
        # Store state for verification
        flow_state['state'] = state
        with open(self._flow_state_file, 'w') as f:
            json.dump(flow_state, f)
        
        logger.info(f"✅ Generated authorization URL (first 100 chars): {authorization_url[:100]}...")
        return authorization_url
    
    def complete_authorization(self, code: str) -> bool:
        """Complete OAuth authorization with authorization code"""
        try:
            # Try to recreate flow from stored state if in-memory flow is missing
            if not self._pending_flow:
                if not os.path.exists(self._flow_state_file):
                    raise Exception("No pending authorization flow. Please start authorization first.")
                
                # Recreate flow from stored state
                flow_state = {}
                with open(self._flow_state_file, 'r') as f:
                    flow_state = json.load(f)
                
                flow = Flow.from_client_secrets_file(
                    self.credentials_file,
                    scopes=flow_state.get('scopes', self.SCOPES),
                    redirect_uri=flow_state.get('redirect_uri', settings.GOOGLE_OAUTH_CALLBACK_URL)
                )
                self._pending_flow = flow
            
            # Exchange code for token
            logger.info(f"🔄 Exchanging authorization code for token...")
            logger.info(f"🔄 Flow state file exists: {os.path.exists(self._flow_state_file)}")
            logger.info(f"🔄 Credentials file: {self.credentials_file} (exists: {os.path.exists(self.credentials_file)})")
            logger.info(f"🔄 Redirect URI: {settings.GOOGLE_OAUTH_CALLBACK_URL}")
            
            self._pending_flow.fetch_token(code=code)
            creds = self._pending_flow.credentials
            
            logger.info(f"✅ Token received, saving credentials...")
            logger.info(f"✅ Has refresh token: {bool(creds.refresh_token)}")
            logger.info(f"✅ Token expires: {creds.expired if hasattr(creds, 'expired') else 'N/A'}")
            
            # Save credentials
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
            
            logger.info(f"✅ Credentials saved to: {self.token_file}")
            
            # Build service with new credentials
            try:
                self.service = build('drive', 'v3', credentials=creds)
                logger.info(f"✅ Drive service built successfully")
                logger.info(f"✅ Service is None: {self.service is None}")
                
                # Verify service works by checking authentication
                if self.service:
                    # Test the service with a simple API call
                    try:
                        self.service.about().get(fields='user').execute()
                        logger.info("✅ Service verified - API call successful")
                    except Exception as e:
                        logger.warning(f"⚠️ Service built but API test failed: {e}")
                else:
                    logger.error("❌ Service is None after build!")
                    
            except Exception as e:
                logger.error(f"❌ Error building Drive service: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.service = None
                return False
            
            self._pending_flow = None
            
            # Clean up flow state file
            if os.path.exists(self._flow_state_file):
                os.remove(self._flow_state_file)
            
            logger.info("✅ Google Drive authorization completed successfully")
            logger.info(f"✅ Final service check - is_authenticated: {self.is_authenticated()}")
            return True
        except Exception as e:
            logger.error(f"❌ Error completing authorization: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._pending_flow = None
            # Clean up flow state file on error
            if os.path.exists(self._flow_state_file):
                os.remove(self._flow_state_file)
            return False

