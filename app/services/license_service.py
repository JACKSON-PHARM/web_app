"""
Email-Based License Service
Manages licensed email addresses for access control
"""
import json
import os
from typing import List, Optional, Tuple
from datetime import datetime
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class LicenseService:
    """Manages email-based licensing"""
    
    def __init__(self):
        self.license_db_path = settings.LICENSE_DB_PATH
        self._ensure_license_db()
    
    def _ensure_license_db(self):
        """Ensure license database exists"""
        if not os.path.exists(self.license_db_path):
            self._save_licenses({
                'licensed_emails': [],
                'admin_emails': [],  # No admin until first registration
                'created_at': datetime.now().isoformat()
            })
            logger.info("✅ Created license database")
    
    def _load_licenses(self) -> dict:
        """Load license database"""
        try:
            with open(self.license_db_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading licenses: {e}")
            return {'licensed_emails': [], 'admin_emails': []}
    
    def _save_licenses(self, data: dict):
        """Save license database"""
        try:
            with open(self.license_db_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving licenses: {e}")
            raise
    
    def is_licensed(self, email: str) -> bool:
        """Check if email is licensed"""
        licenses = self._load_licenses()
        email_lower = email.lower().strip()
        licensed_emails = [e.lower().strip() for e in licenses.get('licensed_emails', [])]
        admin_emails = [e.lower().strip() for e in licenses.get('admin_emails', [])]
        return email_lower in licensed_emails or email_lower in admin_emails
    
    def is_admin(self, email: str) -> bool:
        """Check if email is admin"""
        licenses = self._load_licenses()
        email_lower = email.lower().strip()
        admin_emails = [e.lower().strip() for e in licenses.get('admin_emails', [])]
        return email_lower in admin_emails
    
    def add_license(self, email: str, added_by: str) -> Tuple[bool, str]:
        """Add licensed email (admin only)"""
        if not self.is_admin(added_by):
            return False, "Only admins can add licenses"
        
        licenses = self._load_licenses()
        email_lower = email.lower().strip()
        
        if email_lower not in [e.lower().strip() for e in licenses.get('licensed_emails', [])]:
            licenses['licensed_emails'].append(email)
            licenses['last_updated'] = datetime.now().isoformat()
            licenses['last_updated_by'] = added_by
            self._save_licenses(licenses)
            logger.info(f"✅ Added license for: {email}")
            return True, f"License added for {email}"
        else:
            return False, f"{email} already licensed"
    
    def remove_license(self, email: str, removed_by: str) -> Tuple[bool, str]:
        """Remove licensed email (admin only)"""
        if not self.is_admin(removed_by):
            return False, "Only admins can remove licenses"
        
        licenses = self._load_licenses()
        email_lower = email.lower().strip()
        
        # Don't allow removing admin emails
        if email_lower in [e.lower().strip() for e in licenses.get('admin_emails', [])]:
            return False, "Cannot remove admin email"
        
        licenses['licensed_emails'] = [
            e for e in licenses.get('licensed_emails', [])
            if e.lower().strip() != email_lower
        ]
        licenses['last_updated'] = datetime.now().isoformat()
        licenses['last_updated_by'] = removed_by
        self._save_licenses(licenses)
        logger.info(f"❌ Removed license for: {email}")
        return True, f"License removed for {email}"
    
    def list_licenses(self) -> List[str]:
        """List all licensed emails"""
        licenses = self._load_licenses()
        return licenses.get('licensed_emails', [])
    
    def list_admins(self) -> List[str]:
        """List all admin emails"""
        licenses = self._load_licenses()
        return licenses.get('admin_emails', [])
    
    def get_license_info(self) -> dict:
        """Get license database info"""
        licenses = self._load_licenses()
        return {
            'total_licensed': len(licenses.get('licensed_emails', [])),
            'total_admins': len(licenses.get('admin_emails', [])),
            'created_at': licenses.get('created_at'),
            'last_updated': licenses.get('last_updated'),
            'last_updated_by': licenses.get('last_updated_by')
        }

