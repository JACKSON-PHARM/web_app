"""
Fetcher Manager - Ported for Web Application
Manages data fetchers for refreshing data from APIs
"""
import sys
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import original fetcher manager from scripts
# Note: scripts.fetcher_manager may not exist - this is optional
OriginalFetcherManager = None
try:
    from scripts.fetcher_manager import FetcherManager as OriginalFetcherManager
    logger.info("✅ Imported OriginalFetcherManager from scripts")
except ImportError:
    # This is expected - scripts.fetcher_manager doesn't exist, we use DatabaseFetcherOrchestrator instead
    OriginalFetcherManager = None

class FetcherManager:
    """Fetcher manager for web application"""
    
    def __init__(self, db_manager, app_root, credential_manager):
        self.db_manager = db_manager
        self.app_root = app_root
        self.credential_manager = credential_manager
        
        # Initialize original fetcher manager if available
        if OriginalFetcherManager is not None:
            try:
                self._fetcher_manager = OriginalFetcherManager(
                    db_manager._db_manager,  # Use underlying database manager
                    app_root,
                    credential_manager
                )
                self.logger = logging.getLogger(__name__)
                self.logger.info("✅ Fetcher manager initialized")
            except Exception as e:
                logger.warning(f"⚠️ Could not initialize original fetcher manager: {e}")
                self._fetcher_manager = None
        else:
            self._fetcher_manager = None
            logger.warning("⚠️ Fetcher manager initialized without original fetcher (scripts module not available)")
    
    def refresh_all_data(self) -> Dict[str, Any]:
        """Refresh all data types"""
        results = {}
        
        if self._fetcher_manager is None:
            logger.error("Cannot refresh data: Original fetcher manager not available (scripts module not found)")
            results['success'] = False
            results['message'] = 'Fetcher manager not available - scripts module not found'
            return results
        
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
            logger.error(f"Error refreshing data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            results['success'] = False
            results['message'] = str(e)
        
        return results
    
    def get_fetcher(self, name: str):
        """Get a specific fetcher"""
        if self._fetcher_manager is None:
            logger.warning(f"Cannot get fetcher '{name}': Original fetcher manager not available")
            return None
        return self._fetcher_manager.get_fetcher(name)
    
    def list_fetchers(self) -> list:
        """List all available fetchers"""
        if self._fetcher_manager is None:
            logger.warning("Cannot list fetchers: Original fetcher manager not available")
            return []
        return self._fetcher_manager.list_fetchers()

