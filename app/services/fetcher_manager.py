"""
Fetcher Manager - Ported for Web Application
Manages data fetchers for refreshing data from APIs
"""
import sys
import os
import logging
from typing import Dict, Any, Optional

# Add parent directory to path to import existing fetchers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from scripts.fetcher_manager import FetcherManager as OriginalFetcherManager

logger = logging.getLogger(__name__)

class FetcherManager:
    """Fetcher manager for web application"""
    
    def __init__(self, db_manager, app_root, credential_manager):
        self.db_manager = db_manager
        self.app_root = app_root
        self.credential_manager = credential_manager
        
        # Initialize original fetcher manager
        self._fetcher_manager = OriginalFetcherManager(
            db_manager._db_manager,  # Use underlying database manager
            app_root,
            credential_manager
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("✅ Fetcher manager initialized")
    
    def refresh_all_data(self) -> Dict[str, Any]:
        """Refresh all data types"""
        results = {}
        
        try:
            # Import sync functionality from app_core
            from app_core import PharmaStockApp
            
            # Create a temporary app instance for syncing
            app_instance = PharmaStockApp(app_root=self.app_root)
            app_instance.db = self.db_manager._db_manager
            app_instance.credential_manager = self.credential_manager
            app_instance.fetcher_manager = self._fetcher_manager
            
            # Run sync
            success = app_instance.refresh_all_data()
            
            results['success'] = success
            results['message'] = 'Data refresh completed' if success else 'Data refresh failed'
            
        except Exception as e:
            self.logger.error(f"Error refreshing data: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            results['success'] = False
            results['message'] = str(e)
        
        return results
    
    def get_fetcher(self, name: str):
        """Get a specific fetcher"""
        return self._fetcher_manager.get_fetcher(name)
    
    def list_fetchers(self) -> list:
        """List all available fetchers"""
        return self._fetcher_manager.list_fetchers()

