"""
Refresh Service - Web-compatible data refresh
Runs data fetchers without PyQt5 dependencies
"""
import logging
import sys
import os
from typing import Dict, List, Optional
from app.services.fetcher_manager import FetcherManager
from app.services.database_manager import DatabaseManager
from app.services.credential_manager import CredentialManager

# Add parent directory to import orchestrator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

logger = logging.getLogger(__name__)

class RefreshService:
    """Service for refreshing data from APIs"""
    
    def __init__(self, db_manager: DatabaseManager, app_root: str, credential_manager: CredentialManager):
        self.db_manager = db_manager
        self.app_root = app_root
        self.credential_manager = credential_manager
        self.fetcher_manager = FetcherManager(db_manager, app_root, credential_manager)
        self.logger = logging.getLogger(__name__)
    
    def refresh_all_data(self, companies: Optional[List[str]] = None) -> Dict:
        """Refresh all data types using DatabaseFetcherOrchestrator"""
        results = {
            'success': True,
            'fetchers_run': [],
            'fetchers_failed': [],
            'messages': []
        }
        
        try:
            # Use DatabaseFetcherOrchestrator to run all fetchers properly
            try:
                from scripts.data_fetchers.database_fetcher_orchestrator import DatabaseFetcherOrchestrator
            except ImportError:
                self.logger.error("⚠️ Could not import DatabaseFetcherOrchestrator: No module named 'scripts'")
                results['success'] = False
                results['messages'].append("Data refresh not available - scripts module not found")
                return results
            
            from app.config import settings
            
            self.logger.info("🔄 Initializing DatabaseFetcherOrchestrator...")
            self.logger.info(f"📁 App root: {self.app_root}")
            self.logger.info(f"📁 Database path: {self.db_manager.db_path}")
            
            # Temporarily patch DatabaseBaseFetcher to use the correct database path
            # The orchestrator creates fetchers which use DatabaseBaseFetcher
            # We need to ensure they use the same database as the web app
            original_init = None
            try:
                try:
                    from scripts.data_fetchers.database_base_fetcher import DatabaseBaseFetcher
                except ImportError:
                    self.logger.warning("⚠️ Could not import DatabaseBaseFetcher: No module named 'scripts'")
                    DatabaseBaseFetcher = None
                
                if DatabaseBaseFetcher is None:
                    self.logger.warning("⚠️ Skipping DatabaseBaseFetcher patching - module not available")
                else:
                    # Store original __init__
                    original_init = DatabaseBaseFetcher.__init__
                
                    # Patch to use web app's database path
                    refresh_service_instance = self  # Capture self for closure
                    
                    def patched_init(self_instance, script_name, app_root=None):
                        original_init(self_instance, script_name, app_root or refresh_service_instance.app_root)
                        # Override database path to use web app's database
                        web_db_path = refresh_service_instance.db_manager.db_path
                        if os.path.exists(web_db_path):
                            # Create a new DatabaseManager with the correct path
                            from database_manager import DatabaseManager
                            self_instance.db_manager = DatabaseManager(web_db_path)
                            refresh_service_instance.logger.info(f"✅ Using web app database: {web_db_path}")
                        # Use web app's credential manager
                        self_instance.cred_manager = refresh_service_instance.credential_manager
                    
                    DatabaseBaseFetcher.__init__ = patched_init
                
            except Exception as e:
                self.logger.warning(f"⚠️ Could not patch DatabaseBaseFetcher: {e}")
            
            # Create orchestrator - ensure it uses the web app's database manager
            orchestrator = DatabaseFetcherOrchestrator(app_root=self.app_root)
            
            # Override the base fetcher's database manager to use Supabase
            if hasattr(self.db_manager, 'connection_string'):
                # It's a PostgresDatabaseManager - pass it to fetchers
                self.logger.info("✅ Using Supabase PostgreSQL database manager")
                # The orchestrator's base_fetcher will be used by all fetchers
                # We need to ensure they all use the same database manager
                orchestrator.base_fetcher.db_manager = self.db_manager
                orchestrator.base_fetcher.cred_manager = self.credential_manager
            else:
                self.logger.info("📁 Using SQLite database manager")
            
            # Set up progress callback for logging
            def progress_callback(message, progress=None):
                if progress is not None:
                    self.logger.info(f"[{progress*100:.0f}%] {message}")
                else:
                    self.logger.info(message)
            
            orchestrator.set_progress_callback(progress_callback)
            
            self.logger.info("🚀 Running all fetchers sequentially...")
            
            # Run all fetchers sequentially (this ensures proper order and completion)
            orchestrator_result = orchestrator.run_all_sequential()
            
            # Restore original __init__ if we patched it
            if original_init:
                try:
                    from scripts.data_fetchers.database_base_fetcher import DatabaseBaseFetcher
                    DatabaseBaseFetcher.__init__ = original_init
                    self.logger.info("✅ Restored original DatabaseBaseFetcher.__init__")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not restore original __init__: {e}")
            
            if orchestrator_result.get('success'):
                summary = orchestrator_result.get('summary', {})
                
                # Extract results from orchestrator
                stock_records = summary.get('stock_records', 0)
                grn_count = summary.get('grn_count', 0)
                purchase_orders = summary.get('purchase_orders', 0)
                branch_orders = summary.get('branch_orders', 0)
                supplier_invoices = summary.get('supplier_invoices', 0)
                
                results['fetchers_run'] = ['stock', 'grn', 'orders', 'supplier_invoices']
                results['messages'].extend([
                    f"✅ Stock: {stock_records:,} records updated",
                    f"✅ GRN: {grn_count:,} GRNs processed",
                    f"✅ Purchase Orders: {purchase_orders:,} orders",
                    f"✅ Branch Orders: {branch_orders:,} orders",
                    f"✅ Supplier Invoices: {supplier_invoices:,} invoices"
                ])
                
                results['summary'] = summary
                results['duration'] = orchestrator_result.get('duration', 'Unknown')
                
                self.logger.info(f"✅ Refresh completed successfully in {orchestrator_result.get('duration', 'Unknown')}")
                self.logger.info(f"📊 Summary: Stock={stock_records:,}, GRN={grn_count:,}, Orders={purchase_orders + branch_orders:,}, Invoices={supplier_invoices:,}")
            else:
                results['success'] = False
                error_msg = orchestrator_result.get('message', 'Unknown error')
                results['messages'].append(f"❌ Refresh failed: {error_msg}")
                self.logger.error(f"❌ Refresh failed: {error_msg}")
            
            return results
            
        except ImportError as e:
            self.logger.error(f"❌ Failed to import DatabaseFetcherOrchestrator: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # Fallback to individual fetcher calls
            return self._fallback_refresh(companies)
            
        except Exception as e:
            self.logger.error(f"❌ Error in refresh_all_data: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # Fallback to individual fetcher calls
            return self._fallback_refresh(companies)
    
    def _fallback_refresh(self, companies: Optional[List[str]] = None) -> Dict:
        """Fallback method if orchestrator is not available"""
        results = {
            'success': True,
            'fetchers_run': [],
            'fetchers_failed': [],
            'messages': []
        }
        
        try:
            # Get available fetchers
            available_fetchers = self.fetcher_manager.list_fetchers()
            
            if not available_fetchers:
                results['success'] = False
                results['messages'].append("No data fetchers available")
                return results
            
            # Prioritize fast/urgent datasets
            priority_order = ['stock', 'orders', 'supplier_invoices', 'grn']
            priority_fetchers = [f for f in priority_order if f in available_fetchers]
            
            if not priority_fetchers:
                priority_fetchers = available_fetchers
            
            self.logger.info(f"🔄 Starting fallback refresh: {priority_fetchers}")
            
            # Run priority fetchers
            for fetcher_name in priority_fetchers:
                try:
                    self.logger.info(f"🔄 Running {fetcher_name}...")
                    fetcher = self.fetcher_manager.get_fetcher(fetcher_name)
                    
                    if fetcher:
                        record_count = 0
                        # Try different methods to run the fetcher
                        if hasattr(fetcher, 'fetch_data'):
                            record_count = fetcher.fetch_data(companies) or 0
                        elif hasattr(fetcher, 'run'):
                            result = fetcher.run()
                            if isinstance(result, dict):
                                record_count = result.get('total_updated', 0) or result.get('total_grns', 0) or result.get('total_orders', 0) or result.get('total_invoices', 0) or 0
                            else:
                                record_count = result or 0
                        else:
                            self.logger.warning(f"⚠️ {fetcher_name}: No recognized fetch method")
                        
                        results['fetchers_run'].append(fetcher_name)
                        results['messages'].append(f"✅ {fetcher_name} completed ({record_count:,} records)")
                    else:
                        results['fetchers_failed'].append(fetcher_name)
                        results['messages'].append(f"❌ {fetcher_name} not found")
                        
                except Exception as e:
                    self.logger.error(f"❌ Error running {fetcher_name}: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    results['fetchers_failed'].append(fetcher_name)
                    results['messages'].append(f"❌ {fetcher_name} failed: {str(e)}")
            
            if results['fetchers_failed']:
                results['success'] = False
                results['messages'].append(f"⚠️ Some fetchers failed: {', '.join(results['fetchers_failed'])}")
            else:
                results['messages'].append("✅ All fetchers completed successfully")
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Error in fallback refresh: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e),
                'fetchers_run': results.get('fetchers_run', []),
                'fetchers_failed': results.get('fetchers_failed', []),
                'messages': results.get('messages', []) + [f"❌ Refresh failed: {str(e)}"]
            }

