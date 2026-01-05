"""
Refresh Service - Web-compatible data refresh
Runs data fetchers without PyQt5 dependencies
"""
import logging
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime
from app.services.fetcher_manager import FetcherManager
# CredentialManager can be either local or Supabase - passed as parameter

# Add parent directory to import orchestrator
# __file__ is app/services/refresh_service.py, so we need to go up 2 levels to get to the root
_refresh_service_app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _refresh_service_app_root not in sys.path:
    sys.path.insert(0, _refresh_service_app_root)

logger = logging.getLogger(__name__)

class RefreshService:
    """Service for refreshing data from APIs"""
    
    def __init__(self, db_manager, app_root: str, credential_manager):
        self.db_manager = db_manager
        self.app_root = app_root
        self.credential_manager = credential_manager
        self.fetcher_manager = FetcherManager(db_manager, app_root, credential_manager)
        self.logger = logging.getLogger(__name__)
    
    def refresh_all_data(self, companies: Optional[List[str]] = None) -> Dict:
        """
        Refresh all data types using DatabaseFetcherOrchestrator.
        Uses database-level locking to prevent concurrent refreshes.
        """
        results = {
            'success': True,
            'fetchers_run': [],
            'fetchers_failed': [],
            'messages': []
        }
        
        # Check if refresh is already running (database-level lock)
        # Gracefully handle if lock functions don't exist
        lock_functions_available = True
        try:
            if hasattr(self.db_manager, 'is_refresh_locked'):
                try:
                    if self.db_manager.is_refresh_locked('global'):
                        self.logger.warning("⚠️ Refresh already in progress - skipping duplicate request")
                        results['success'] = False
                        results['messages'].append("⚠️ Refresh already in progress. Please wait for the current refresh to complete.")
                        return results
                except ValueError as ve:
                    # Lock functions don't exist - continue without lock
                    lock_functions_available = False
                    self.logger.info("ℹ️ Lock functions not available - continuing refresh without lock check")
                except Exception as lock_check_error:
                    # Other error - log and continue
                    self.logger.debug(f"⚠️ Could not check refresh lock: {lock_check_error}")
        except Exception as e:
            self.logger.debug(f"⚠️ Refresh lock check not available: {e}")
        
        # Acquire refresh lock (database-level, prevents concurrent refreshes)
        # Gracefully handle if lock functions don't exist
        lock_acquired = True  # Default to True if lock functions don't exist
        try:
            if hasattr(self.db_manager, 'acquire_refresh_lock') and lock_functions_available:
                try:
                    lock_acquired = self.db_manager.acquire_refresh_lock('global', timeout_seconds=7200)  # 2 hour timeout
                    if not lock_acquired:
                        # Lock is already held by another process
                        self.logger.warning("⚠️ Could not acquire refresh lock - another refresh is running")
                        results['success'] = False
                        results['messages'].append("⚠️ Another refresh is currently running. Please wait for it to complete.")
                        return results
                except ValueError as ve:
                    # Lock functions don't exist - continue without lock
                    lock_functions_available = False
                    lock_acquired = True
                    self.logger.info("ℹ️ Lock functions not available - continuing refresh without lock")
                except Exception as lock_acquire_error:
                    # Some other error - log and continue
                    self.logger.warning(f"⚠️ Could not acquire refresh lock: {lock_acquire_error}")
                    self.logger.info("ℹ️ Continuing refresh without lock")
                    lock_acquired = True
        except Exception as e:
            self.logger.debug(f"⚠️ Refresh lock acquisition not available: {e}")
            self.logger.info("ℹ️ Continuing refresh without lock")
            lock_functions_available = False
        
        try:
            # Use DatabaseFetcherOrchestrator to run all fetchers properly
            # Ensure app_root is in sys.path for imports
            if self.app_root and self.app_root not in sys.path:
                sys.path.insert(0, self.app_root)
            try:
                from scripts.data_fetchers.database_fetcher_orchestrator import DatabaseFetcherOrchestrator
            except ImportError as import_error:
                self.logger.error(f"⚠️ Could not import DatabaseFetcherOrchestrator: {import_error}")
                self.logger.error(f"   App root: {self.app_root}")
                self.logger.error(f"   Scripts path exists: {os.path.exists(os.path.join(self.app_root, 'scripts')) if self.app_root else False}")
                self.logger.error(f"   sys.path (first 5): {sys.path[:5]}")
                results['success'] = False
                results['messages'].append(f"Data refresh not available - scripts module not found: {import_error}")
                return results
            
            from app.config import settings
            
            self.logger.info("🔄 Initializing DatabaseFetcherOrchestrator...")
            self.logger.info(f"📁 App root: {self.app_root}")
            # Check if PostgreSQL (doesn't have db_path)
            is_postgres = hasattr(self.db_manager, 'connection_string') or hasattr(self.db_manager, 'pool') or 'PostgresDatabaseManager' in str(type(self.db_manager))
            if is_postgres:
                self.logger.info("📁 Database: Supabase PostgreSQL")
            else:
                self.logger.info(f"📁 Database path: {self.db_manager.db_path if hasattr(self.db_manager, 'db_path') else 'None'}")
            
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
                        # Override database manager to use web app's database manager
                        # Check if PostgreSQL (doesn't have db_path)
                        is_postgres = hasattr(refresh_service_instance.db_manager, 'connection_string') or hasattr(refresh_service_instance.db_manager, 'pool') or 'PostgresDatabaseManager' in str(type(refresh_service_instance.db_manager))
                        
                        if is_postgres:
                            # PostgreSQL - use the web app's database manager directly
                            self_instance.db_manager = refresh_service_instance.db_manager
                            refresh_service_instance.logger.info("✅ Using web app Supabase PostgreSQL database")
                        # No SQLite fallback - always use PostgreSQL
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
            
            # Set up progress callback for logging and status updates
            from app.services.refresh_status import RefreshStatusService
            
            def progress_callback(message, progress=None):
                if progress is not None:
                    self.logger.info(f"[{progress*100:.0f}%] {message}")
                    RefreshStatusService.update_progress(progress, message)
                else:
                    self.logger.info(message)
                    RefreshStatusService.update_progress(None, message)
            
            orchestrator.set_progress_callback(progress_callback)
            
            # Get refresh_started timestamp (set when refresh started)
            refresh_started = RefreshStatusService.get_status().get("refresh_started")
            if not refresh_started:
                refresh_started = datetime.now().isoformat()
                self.logger.warning("⚠️ refresh_started not found in status - using current time")
            
            self.logger.info("🚀 Running all fetchers in parallel for faster execution...")
            self.logger.info(f"📅 Refresh started at: {refresh_started}")
            
            # Run all fetchers in parallel to reduce total time
            # Supabase free tier allows concurrent connections, so we can parallelize safely
            orchestrator_result = orchestrator.run_all_parallel(refresh_started=refresh_started)
            
            # Restore original __init__ if we patched it
            if original_init:
                try:
                    from scripts.data_fetchers.database_base_fetcher import DatabaseBaseFetcher
                    DatabaseBaseFetcher.__init__ = original_init
                    self.logger.info("✅ Restored original DatabaseBaseFetcher.__init__")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not restore original __init__: {e}")
            
            # Run sanity checks after fetchers complete
            self.logger.info("🔍 Running sanity checks...")
            from app.services.sanity_checks import SanityCheckService
            from scripts.data_fetchers.branch_config import ALL_BRANCHES
            
            sanity_service = SanityCheckService(self.db_manager)
            sanity_results = sanity_service.check_all_branches_sanity(ALL_BRANCHES, refresh_started)
            
            # Delete old branch stock ONLY for branches that passed sanity
            self.logger.info("🧹 Cleaning up old branch stock (only for branches that passed sanity)...")
            for branch_name, branch_status in sanity_results["branches"].items():
                if branch_status["status"] == "success":
                    # Find branch info to get company
                    branch_info = next((b for b in ALL_BRANCHES if b["branch_name"] == branch_name), None)
                    if branch_info:
                        company = branch_info.get("company")
                        if company:
                            deleted = self.db_manager.delete_branch_stock(branch_name, company, refresh_started)
                            if deleted > 0:
                                self.logger.info(f"✅ Deleted {deleted:,} old stock rows for {branch_name}")
                else:
                    self.logger.warning(f"⚠️ Skipping stock deletion for {branch_name} - sanity check failed: {branch_status.get('reason')}")
            
            # Determine overall refresh outcome
            all_branches_success = all(
                status["status"] == "success" 
                for status in sanity_results["branches"].values()
            )
            any_branch_success = any(
                status["status"] == "success" 
                for status in sanity_results["branches"].values()
            )
            
            if all_branches_success:
                refresh_outcome = "success"
            elif any_branch_success:
                refresh_outcome = "partial"
            else:
                refresh_outcome = "failed"
            
            # ⚠️ HARD CONSTRAINT: Never mark success unless all sanity checks pass
            if refresh_outcome != "success":
                results['success'] = False
                self.logger.warning(f"⚠️ Refresh outcome is {refresh_outcome} - NOT marking as successful")
            else:
                results['success'] = True
                self.logger.info("✅ All sanity checks passed - refresh is successful")
            
            if orchestrator_result.get('success'):
                summary = orchestrator_result.get('summary', {})
                
                # Extract results from orchestrator
                stock_records = summary.get('stock_records', 0)
                purchase_orders = summary.get('purchase_orders', 0)
                branch_orders = summary.get('branch_orders', 0)
                supplier_invoices = summary.get('supplier_invoices', 0)
                
                results['fetchers_run'] = ['stock', 'orders', 'supplier_invoices']
                results['messages'].extend([
                    f"✅ Stock: {stock_records:,} records updated",
                    f"✅ Purchase Orders: {purchase_orders:,} orders",
                    f"✅ Branch Orders: {branch_orders:,} orders",
                    f"✅ Supplier Invoices: {supplier_invoices:,} invoices"
                ])
                
                # Add sanity check results to messages
                if refresh_outcome == "partial":
                    failed_branches = [
                        name for name, status in sanity_results["branches"].items()
                        if status["status"] == "failed"
                    ]
                    results['messages'].append(f"⚠️ Partial refresh: {len(failed_branches)} branch(es) failed sanity checks")
                elif refresh_outcome == "failed":
                    results['messages'].append("❌ Refresh failed: All branches failed sanity checks")
                
                results['summary'] = summary
                results['duration'] = orchestrator_result.get('duration', 'Unknown')
                results['refresh_outcome'] = refresh_outcome
                results['sanity_results'] = sanity_results
                
                self.logger.info(f"📊 Refresh outcome: {refresh_outcome}")
                self.logger.info(f"📊 Summary: Stock={stock_records:,}, Orders={purchase_orders + branch_orders:,}, Invoices={supplier_invoices:,}")
            else:
                results['success'] = False
                error_msg = orchestrator_result.get('message', 'Unknown error')
                results['messages'].append(f"❌ Refresh failed: {error_msg}")
                results['refresh_outcome'] = "failed"
                self.logger.error(f"❌ Refresh failed: {error_msg}")
            
            # Update refresh status with outcome and branch/report status
            RefreshStatusService.set_refresh_complete(
                success=(refresh_outcome == "success"),
                refresh_outcome=refresh_outcome,
                branches=sanity_results["branches"],
                reports=sanity_results["reports"]
            )
            
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
        finally:
            # Release refresh lock if we acquired it and functions are available
            if lock_acquired and lock_functions_available and hasattr(self.db_manager, 'release_refresh_lock'):
                try:
                    self.db_manager.release_refresh_lock('global')
                    self.logger.debug("🔓 Released refresh lock")
                except Exception as release_error:
                    self.logger.debug(f"⚠️ Could not release refresh lock: {release_error}")
    
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
            priority_order = ['stock', 'orders', 'supplier_invoices']
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
                                record_count = result.get('total_updated', 0) or result.get('total_orders', 0) or result.get('total_invoices', 0) or 0
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
            
            # Materialized views removed - no refresh needed
            # Data is always fresh via stock_snapshot() function
            
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
    
    def refresh_selected_data(self, fetchers: List[str]) -> Dict:
        """Refresh only selected fetchers"""
        results = {
            'success': True,
            'fetchers_run': [],
            'fetchers_failed': [],
            'messages': []
        }
        
        try:
            # Use DatabaseFetcherOrchestrator to run selected fetchers
            # Ensure app_root is in sys.path for imports
            if self.app_root and self.app_root not in sys.path:
                sys.path.insert(0, self.app_root)
            try:
                from scripts.data_fetchers.database_fetcher_orchestrator import DatabaseFetcherOrchestrator
            except ImportError as import_error:
                self.logger.error(f"⚠️ Could not import DatabaseFetcherOrchestrator: {import_error}")
                self.logger.error(f"   App root: {self.app_root}")
                self.logger.error(f"   Scripts path exists: {os.path.exists(os.path.join(self.app_root, 'scripts')) if self.app_root else False}")
                self.logger.error(f"   sys.path (first 5): {sys.path[:5]}")
                results['success'] = False
                results['messages'].append(f"Data refresh not available - scripts module not found: {import_error}")
                return results
            
            from app.config import settings
            
            self.logger.info(f"🔄 Initializing DatabaseFetcherOrchestrator for fetchers: {fetchers}...")
            
            # Create orchestrator
            orchestrator = DatabaseFetcherOrchestrator(app_root=self.app_root)
            
            # Override the base fetcher's database manager to use Supabase
            if hasattr(self.db_manager, 'connection_string') or hasattr(self.db_manager, 'pool'):
                self.logger.info("✅ Using Supabase PostgreSQL database manager")
                orchestrator.base_fetcher.db_manager = self.db_manager
                orchestrator.base_fetcher.cred_manager = self.credential_manager
            
            # Set up progress callback
            from app.services.refresh_status import RefreshStatusService
            
            def progress_callback(message, progress=None):
                if progress is not None:
                    self.logger.info(f"[{progress*100:.0f}%] {message}")
                    RefreshStatusService.update_progress(progress, message)
                else:
                    self.logger.info(message)
                    RefreshStatusService.update_progress(None, message)
            
            orchestrator.set_progress_callback(progress_callback)
            
            self.logger.info(f"🚀 Running selected fetchers: {fetchers}...")
            
            # Run selected fetchers
            orchestrator_result = orchestrator.run_selected(fetchers)
            
            if orchestrator_result.get('success'):
                fetcher_results = orchestrator_result.get('results', {})
                
                for fetcher_name in fetchers:
                    fetcher_result = fetcher_results.get(fetcher_name, {})
                    if fetcher_result.get('success'):
                        results['fetchers_run'].append(fetcher_name)
                        # Extract count based on fetcher type
                        count = 0
                        if fetcher_name == 'stock':
                            count = fetcher_result.get('total_updated', 0)
                        elif fetcher_name == 'orders':
                            count = fetcher_result.get('total_orders', 0) or (
                                fetcher_result.get('total_purchase_orders', 0) + 
                                fetcher_result.get('total_branch_orders', 0)
                            )
                        elif fetcher_name == 'supplier_invoices':
                            count = fetcher_result.get('total_invoices', 0)
                        
                        results['messages'].append(f"✅ {fetcher_name}: {count:,} records processed")
                    else:
                        results['fetchers_failed'].append(fetcher_name)
                        error_msg = fetcher_result.get('message', 'Unknown error')
                        results['messages'].append(f"❌ {fetcher_name} failed: {error_msg}")
                
                results['summary'] = fetcher_results
                results['duration'] = orchestrator_result.get('duration', 'Unknown')
                
                self.logger.info(f"✅ Selected fetchers completed in {orchestrator_result.get('duration', 'Unknown')}")
                
                # Materialized views removed - no refresh needed
                # Data is always fresh via stock_snapshot() function
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
            results['success'] = False
            results['messages'].append(f"Import error: {str(e)}")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Error in refresh_selected_data: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            results['success'] = False
            results['messages'].append(f"Error: {str(e)}")
            return results

    # Materialized views have been removed - no refresh needed
    # Data is always fresh via stock_snapshot() function
    # This method is kept for backward compatibility but does nothing
    def _refresh_materialized_views(self):
        """Materialized views removed - no refresh needed"""
        self.logger.debug("ℹ️ Materialized views removed - using stock_snapshot() function for fresh data")
        pass

