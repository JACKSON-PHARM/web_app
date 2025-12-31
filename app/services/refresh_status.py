"""
Refresh Status Tracking Service
Tracks refresh progress and last update times
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from app.config import settings

logger = logging.getLogger(__name__)

STATUS_FILE = os.path.join(settings.LOCAL_CACHE_DIR, "refresh_status.json")

class RefreshStatusService:
    """Service for tracking refresh status and data freshness"""
    
    @staticmethod
    def get_status() -> Dict:
        """Get current refresh status"""
        try:
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading status file: {e}")
        
        return {
            "is_refreshing": False,
            "last_refresh": None,
            "refresh_started": None,
            "refresh_progress": None,
            "refresh_message": None,
            "is_uploading": False,
            "upload_progress": None,
            "upload_message": None,
            "upload_size_mb": None,
            "refresh_outcome": None,  # "success" | "partial" | "failed"
            "branches": {},  # {"BranchName": {"status": "success|failed", "reason": "..."}}
            "reports": {}  # {"stock": "success|partial|failed", "orders": "success|partial|failed", ...}
        }
    
    @staticmethod
    def set_refreshing(is_refreshing: bool, message: Optional[str] = None):
        """Set refresh status"""
        status = RefreshStatusService.get_status()
        status["is_refreshing"] = is_refreshing
        if is_refreshing:
            # Store the timestamp when refresh started (before any DB modifications)
            status["refresh_started"] = datetime.now().isoformat()
            status["refresh_message"] = message or "Refreshing data..."
        else:
            # Don't clear refresh_started immediately - keep it for a bit to check if DB was modified
            status["refresh_message"] = None
        
        RefreshStatusService._save_status(status)
    
    @staticmethod
    def set_refresh_complete(success: bool = True, message: Optional[str] = None,
                            refresh_outcome: Optional[str] = None,
                            branches: Optional[Dict] = None,
                            reports: Optional[Dict] = None):
        """
        Mark refresh as complete
        
        ⚠️ HARD CONSTRAINT: Never call set_refresh_complete(success=True) unless all sanity checks pass.
        Fetch success ≠ data correctness. Sanity validation is mandatory before marking success.
        
        Args:
            success: Whether refresh completed (deprecated - use refresh_outcome instead)
            message: Optional message
            refresh_outcome: "success" | "partial" | "failed"
            branches: Branch-level status {"BranchName": {"status": "success|failed", "reason": "..."}}
            reports: Report-level status {"stock": "success|partial|failed", "orders": "success|partial|failed", ...}
        """
        status = RefreshStatusService.get_status()
        status["is_refreshing"] = False
        # Keep refresh_started for a bit to check if DB was modified
        # It will be cleared on next refresh start
        status["refresh_message"] = None
        
        # Set refresh outcome (mandatory for sanity-aware refresh)
        if refresh_outcome:
            status["refresh_outcome"] = refresh_outcome
        elif success:
            # Legacy mode: if no refresh_outcome provided, infer from success
            # But warn that this should not be used for sanity-aware refresh
            status["refresh_outcome"] = "success"
            logger.warning("⚠️ set_refresh_complete called with success=True but no refresh_outcome - using legacy mode")
        else:
            status["refresh_outcome"] = "failed"
        
        # Set branch-level status
        if branches:
            status["branches"] = branches
        
        # Set report-level status
        if reports:
            status["reports"] = reports
        
        # Only update last_refresh if refresh was successful (all sanity checks passed)
        if status["refresh_outcome"] == "success":
            status["last_refresh"] = datetime.now().isoformat()
        else:
            # Don't update last_refresh on partial/failed - data is not trustworthy
            logger.warning(f"⚠️ Refresh outcome is {status['refresh_outcome']} - not updating last_refresh timestamp")
        
        RefreshStatusService._save_status(status)
    
    @staticmethod
    def update_progress(progress: Optional[float] = None, message: Optional[str] = None):
        """Update refresh progress"""
        status = RefreshStatusService.get_status()
        if progress is not None:
            status["refresh_progress"] = progress
        if message:
            status["refresh_message"] = message
        
        RefreshStatusService._save_status(status)
    
    @staticmethod
    def _save_status(status: Dict):
        """Save status to file"""
        try:
            os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
            with open(STATUS_FILE, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving status file: {e}")
    
    @staticmethod
    def set_uploading(size_mb: float):
        """Set upload status to uploading"""
        status = RefreshStatusService.get_status()
        status["is_uploading"] = True
        status["upload_progress"] = 0
        status["upload_message"] = "Starting upload..."
        status["upload_size_mb"] = size_mb
        RefreshStatusService._save_status(status)
    
    @staticmethod
    def update_upload_progress(progress: float, message: Optional[str] = None):
        """Update upload progress (0-100)"""
        status = RefreshStatusService.get_status()
        status["upload_progress"] = progress
        if message:
            status["upload_message"] = message
        RefreshStatusService._save_status(status)
    
    @staticmethod
    def set_upload_complete():
        """Mark upload as complete"""
        status = RefreshStatusService.get_status()
        status["is_uploading"] = False
        status["upload_progress"] = 100
        status["upload_message"] = "Upload completed successfully"
        RefreshStatusService._save_status(status)
    
    @staticmethod
    def set_upload_failed(error_message: Optional[str] = None):
        """Mark upload as failed"""
        status = RefreshStatusService.get_status()
        status["is_uploading"] = False
        status["upload_progress"] = None
        status["upload_message"] = error_message or "Upload failed"
        RefreshStatusService._save_status(status)
    
    @staticmethod
    def get_data_age() -> Optional[Dict]:
        """Get human-readable data age"""
        status = RefreshStatusService.get_status()
        last_refresh = status.get("last_refresh")
        
        if not last_refresh:
            return {
                "age": None,
                "message": "Never updated",
                "is_stale": True
            }
        
        try:
            last_refresh_dt = datetime.fromisoformat(last_refresh)
            now = datetime.now()
            delta = now - last_refresh_dt
            
            total_seconds = int(delta.total_seconds())
            minutes = total_seconds // 60
            hours = minutes // 60
            days = hours // 24
            
            if days > 0:
                message = f"{days} day{'s' if days > 1 else ''} ago"
                is_stale = days >= 1
            elif hours > 0:
                message = f"{hours} hour{'s' if hours > 1 else ''} ago"
                is_stale = hours >= 3
            elif minutes > 0:
                message = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                is_stale = minutes >= 30
            else:
                message = "Just now"
                is_stale = False
            
            return {
                "age": total_seconds,
                "message": message,
                "is_stale": is_stale,
                "last_refresh": last_refresh
            }
        except Exception as e:
            logger.error(f"Error calculating data age: {e}")
            return {
                "age": None,
                "message": "Unknown",
                "is_stale": True
            }

