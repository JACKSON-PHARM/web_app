"""
Database Fetcher Orchestrator
Runs all database-backed fetchers in sequence or parallel
Can be run from frontend or as a background service
"""
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import threading
import time

# Add app root to path
app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, app_root)

from scripts.data_fetchers.database_base_fetcher import DatabaseBaseFetcher
from scripts.data_fetchers.database_stock_fetcher import DatabaseStockFetcher
from scripts.data_fetchers.database_orders_fetcher import DatabaseOrdersFetcher
from scripts.data_fetchers.database_supplier_invoices_fetcher import DatabaseSupplierInvoicesFetcher

# Try to import HQ invoices fetcher (may not exist in all environments)
try:
    from scripts.data_fetchers.database_hq_invoices_fetcher import DatabaseHQInvoicesFetcher
    HQ_INVOICES_AVAILABLE = True
except ImportError:
    HQ_INVOICES_AVAILABLE = False
    DatabaseHQInvoicesFetcher = None


class DatabaseFetcherOrchestrator:
    """
    Orchestrator for running all database-backed fetchers
    Can run sequentially or in parallel
    """
    
    def __init__(self, app_root: str = None):
        self.app_root = app_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.base_fetcher = DatabaseBaseFetcher("orchestrator", self.app_root)
        self.results = {}
        self.is_running = False
        self.progress_callback = None
        
    def set_progress_callback(self, callback):
        """Set callback function for progress updates"""
        self.progress_callback = callback
    
    def _update_progress(self, message: str, progress: float = None):
        """Update progress if callback is set"""
        if self.progress_callback:
            self.progress_callback(message, progress)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    
    def run_stock_fetcher(self) -> Dict:
        """Run stock position fetcher"""
        self._update_progress("Starting Stock Position Sync...", 0.0)
        try:
            # Use the base fetcher's database manager and credential manager
            fetcher = DatabaseStockFetcher(
                self.app_root,
                db_manager=self.base_fetcher.db_manager,
                credential_manager=self.base_fetcher.cred_manager
            )
            result = fetcher.run()
            self.results['stock'] = result
            return result
        except Exception as e:
            error_result = {"success": False, "message": str(e)}
            self.results['stock'] = error_result
            return error_result
    
    def run_orders_fetcher(self) -> Dict:
        """Run orders fetcher"""
        self._update_progress("Starting Orders Download...", 0.4)
        try:
            fetcher = DatabaseOrdersFetcher(
                self.app_root,
                db_manager=self.base_fetcher.db_manager,
                credential_manager=self.base_fetcher.cred_manager
            )
            result = fetcher.run()
            self.results['orders'] = result
            return result
        except Exception as e:
            error_result = {"success": False, "message": str(e)}
            self.results['orders'] = error_result
            return error_result
    
    def run_supplier_invoices_fetcher(self) -> Dict:
        """Run supplier invoices fetcher"""
        self._update_progress("Starting Supplier Invoices Download...", 0.6)
        try:
            fetcher = DatabaseSupplierInvoicesFetcher(
                self.app_root,
                db_manager=self.base_fetcher.db_manager,
                credential_manager=self.base_fetcher.cred_manager
            )
            result = fetcher.run()
            self.results['supplier_invoices'] = result
            return result
        except Exception as e:
            error_result = {"success": False, "message": str(e)}
            self.results['supplier_invoices'] = error_result
            return error_result
    
    def run_cleanup(self) -> Dict:
        """Run cleanup of old data (older than 30 days)"""
        try:
            # Import cleanup function
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cleanup_script = os.path.join(script_dir, "cleanup_old_data.py")
            
            if not os.path.exists(cleanup_script):
                self._update_progress("⚠️ Cleanup script not found, skipping...")
                return {"success": False, "message": "Cleanup script not found"}
            
            # Get connection string from base fetcher's db_manager
            try:
                if hasattr(self.base_fetcher.db_manager, 'connection_string'):
                    connection_string = self.base_fetcher.db_manager.connection_string
                else:
                    # Try to get from config
                    from app.config import settings
                    connection_string = settings.DATABASE_URL
                
                if not connection_string:
                    return {"success": False, "message": "No database connection string"}
                
                # Import and run cleanup
                import sys
                sys.path.insert(0, script_dir)
                from cleanup_old_data import cleanup_old_data
                
                result = cleanup_old_data(connection_string, retention_days=30)
                
                if isinstance(result, dict):
                    return result
                elif result:
                    return {"success": True, "total_deleted": 0, "message": "Cleanup completed"}
                else:
                    return {"success": False, "total_deleted": 0, "message": "Cleanup failed"}
            except Exception as e:
                self._update_progress(f"⚠️ Cleanup error: {e}")
                return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def run_hq_invoices_fetcher(self) -> Dict:
        """Run HQ invoices fetcher (invoices and branch transfers from BABA DOGO HQ)"""
        if not HQ_INVOICES_AVAILABLE:
            self._update_progress("HQ Invoices fetcher not available, skipping...", 0.7)
            return {"success": False, "message": "HQ Invoices fetcher not available"}
        
        self._update_progress("Starting HQ Invoices Download...", 0.7)
        try:
            # Get database manager and credential manager from base fetcher
            db_manager = self.base_fetcher.db_manager
            cred_manager = self.base_fetcher.cred_manager
            
            fetcher = DatabaseHQInvoicesFetcher(db_manager, cred_manager)
            count = fetcher.fetch_data()  # Fetches last 90 days by default
            
            result = {
                "success": True,
                "message": f"Fetched {count} HQ invoice/transfer records",
                "records_processed": count
            }
            self.results['hq_invoices'] = result
            return result
        except Exception as e:
            error_result = {"success": False, "message": str(e)}
            self.results['hq_invoices'] = error_result
            import traceback
            self.base_fetcher.logger.error(traceback.format_exc())
            return error_result
    
    def run_all_sequential(self) -> Dict:
        """
        Run all fetchers sequentially
        Returns summary of all results
        """
        if self.is_running:
            return {"success": False, "message": "Orchestrator is already running"}
        
        self.is_running = True
        self.results = {}
        start_time = datetime.now()
        
        try:
            self._update_progress("=" * 70)
            self._update_progress("🚀 DATABASE FETCHER ORCHESTRATOR - SEQUENTIAL MODE")
            self._update_progress("=" * 70)
            
            # Validate prerequisites
            if not self.base_fetcher.validate_prerequisites():
                return {"success": False, "message": "No companies configured"}
            
            # Run all fetchers in sequence
            stock_result = self.run_stock_fetcher()
            self._update_progress(f"✅ Stock: {stock_result.get('total_updated', 0)} records", 0.33)
            
            orders_result = self.run_orders_fetcher()
            self._update_progress(f"✅ Orders: {orders_result.get('total_orders', 0)} orders", 0.66)
            
            supplier_result = self.run_supplier_invoices_fetcher()
            self._update_progress(f"✅ Supplier Invoices: {supplier_result.get('total_invoices', 0)} invoices", 0.85)
            
            # Run HQ invoices fetcher (invoices and transfers from BABA DOGO HQ)
            hq_invoices_result = self.run_hq_invoices_fetcher()
            self._update_progress(f"✅ HQ Invoices: {hq_invoices_result.get('records_processed', 0)} records", 0.95)
            
            # Run cleanup of old data (older than 30 days)
            self._update_progress("🧹 Cleaning up old data (older than 30 days)...", 0.98)
            cleanup_result = self.run_cleanup()
            if cleanup_result.get('success'):
                self._update_progress(f"✅ Cleanup: {cleanup_result.get('total_deleted', 0):,} records deleted", 0.99)
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            # Summary
            summary = {
                "success": True,
                "duration": str(duration),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "results": {
                    "stock": stock_result,
                    "orders": orders_result,
                    "supplier_invoices": supplier_result,
                    "hq_invoices": hq_invoices_result,
                    "cleanup": cleanup_result if 'cleanup_result' in locals() else {"success": False, "message": "Not run"}
                },
                "summary": {
                    "stock_records": stock_result.get('total_updated', 0),
                    "purchase_orders": orders_result.get('total_purchase_orders', 0),
                    "branch_orders": orders_result.get('total_branch_orders', 0),
                    "supplier_invoices": supplier_result.get('total_invoices', 0)
                }
            }
            
            self._update_progress("=" * 70)
            self._update_progress("🎉 ALL FETCHERS COMPLETED!")
            self._update_progress("=" * 70)
            self._update_progress(f"⏱️  Total Time: {duration}", 1.0)
            self._update_progress(f"📊 Stock Records: {summary['summary']['stock_records']:,}")
            self._update_progress(f"📊 GRNs: {summary['summary']['grn_count']:,}")
            self._update_progress(f"📊 Purchase Orders: {summary['summary']['purchase_orders']:,}")
            self._update_progress(f"📊 Branch Orders: {summary['summary']['branch_orders']:,}")
            self._update_progress(f"📊 Supplier Invoices: {summary['summary']['supplier_invoices']:,}")
            self._update_progress("=" * 70)
            
            return summary
            
        except Exception as e:
            error_msg = f"Orchestrator error: {str(e)}"
            self._update_progress(f"❌ {error_msg}")
            return {"success": False, "message": error_msg}
        finally:
            self.is_running = False
    
    def run_all_parallel(self) -> Dict:
        """
        Run all fetchers in parallel for faster execution
        Supabase free tier allows concurrent connections, so we can parallelize safely
        This significantly reduces total refresh time
        """
        if self.is_running:
            return {"success": False, "message": "Orchestrator is already running"}
        
        self.is_running = True
        self.results = {}
        start_time = datetime.now()
        
        try:
            self._update_progress("=" * 70)
            self._update_progress("🚀 DATABASE FETCHER ORCHESTRATOR - PARALLEL MODE")
            self._update_progress("=" * 70)
            self._update_progress("⚡ Running all fetchers in parallel for maximum speed...", 0.0)
            
            # Validate prerequisites
            if not self.base_fetcher.validate_prerequisites():
                return {"success": False, "message": "No companies configured"}
            
            # Run fetchers in parallel using threads
            threads = []
            results = {}
            results_lock = threading.Lock()
            
            def run_with_result(fetcher_name, fetcher_func):
                try:
                    self._update_progress(f"🔄 Starting {fetcher_name} fetcher...")
                    result = fetcher_func()
                    with results_lock:
                        results[fetcher_name] = result
                    if result.get('success'):
                        self._update_progress(f"✅ {fetcher_name} completed successfully")
                    else:
                        self._update_progress(f"⚠️ {fetcher_name} completed with errors: {result.get('message', 'Unknown error')}")
                except Exception as e:
                    with results_lock:
                        results[fetcher_name] = {"success": False, "message": str(e)}
                    self._update_progress(f"❌ {fetcher_name} failed: {str(e)}")
            
            # Start all main fetchers in parallel
            t1 = threading.Thread(target=run_with_result, args=("stock", self.run_stock_fetcher), daemon=False)
            t2 = threading.Thread(target=run_with_result, args=("orders", self.run_orders_fetcher), daemon=False)
            t3 = threading.Thread(target=run_with_result, args=("supplier_invoices", self.run_supplier_invoices_fetcher), daemon=False)
            
            threads = [t1, t2, t3]
            
            # Start all threads
            self._update_progress("🚀 Starting all fetchers in parallel...", 0.1)
            for t in threads:
                t.start()
            
            # Wait for all main fetchers to complete
            for t in threads:
                t.join()
            
            # Run HQ invoices fetcher (can run after main fetchers, or in parallel if needed)
            if HQ_INVOICES_AVAILABLE:
                self._update_progress("🔄 Starting HQ Invoices fetcher...", 0.85)
                hq_result = self.run_hq_invoices_fetcher()
                results['hq_invoices'] = hq_result
            
            # Run cleanup after all data is fetched (must be sequential)
            self._update_progress("🧹 Cleaning up old data (older than 30 days)...", 0.95)
            cleanup_result = self.run_cleanup()
            results['cleanup'] = cleanup_result
            if cleanup_result.get('success'):
                self._update_progress(f"✅ Cleanup: {cleanup_result.get('total_deleted', 0):,} records deleted", 0.98)
            
            self.results = results
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            # Summary
            summary = {
                "success": True,
                "duration": str(duration),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "results": results,
                "summary": {
                    "stock_records": results.get("stock", {}).get('total_updated', 0),
                    "purchase_orders": results.get("orders", {}).get('total_purchase_orders', 0),
                    "branch_orders": results.get("orders", {}).get('total_branch_orders', 0),
                    "supplier_invoices": results.get("supplier_invoices", {}).get('total_invoices', 0),
                    "hq_invoices": results.get("hq_invoices", {}).get('records_processed', 0)
                }
            }
            
            self._update_progress("=" * 70)
            self._update_progress("🎉 ALL FETCHERS COMPLETED!")
            self._update_progress("=" * 70)
            self._update_progress(f"⏱️  Total Time: {duration}", 1.0)
            self._update_progress(f"📊 Stock Records: {summary['summary']['stock_records']:,}")
            self._update_progress(f"📊 Purchase Orders: {summary['summary']['purchase_orders']:,}")
            self._update_progress(f"📊 Branch Orders: {summary['summary']['branch_orders']:,}")
            self._update_progress(f"📊 Supplier Invoices: {summary['summary']['supplier_invoices']:,}")
            if summary['summary'].get('hq_invoices', 0) > 0:
                self._update_progress(f"📊 HQ Invoices: {summary['summary']['hq_invoices']:,}")
            self._update_progress("=" * 70)
            
            return summary
            
        except Exception as e:
            error_msg = f"Orchestrator error: {str(e)}"
            self._update_progress(f"❌ {error_msg}")
            import traceback
            self.base_fetcher.logger.error(traceback.format_exc())
            return {"success": False, "message": error_msg}
        finally:
            self.is_running = False
    
    def run_selected(self, fetchers: List[str]) -> Dict:
        """
        Run only selected fetchers
        fetchers: List of fetcher names ['stock', 'grn', 'orders', 'supplier_invoices']
        """
        if self.is_running:
            return {"success": False, "message": "Orchestrator is already running"}
        
        self.is_running = True
        self.results = {}
        start_time = datetime.now()
        
        try:
            fetcher_map = {
                'stock': self.run_stock_fetcher,
                'orders': self.run_orders_fetcher,
                'supplier_invoices': self.run_supplier_invoices_fetcher
            }
            
            for fetcher_name in fetchers:
                if fetcher_name in fetcher_map:
                    fetcher_map[fetcher_name]()
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            return {
                "success": True,
                "duration": str(duration),
                "results": self.results
            }
            
        except Exception as e:
            return {"success": False, "message": str(e)}
        finally:
            self.is_running = False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Fetcher Orchestrator')
    parser.add_argument('--mode', choices=['sequential', 'parallel'], 
                       default='sequential', help='Execution mode')
    parser.add_argument('--fetchers', nargs='+', 
                       choices=['stock', 'orders', 'supplier_invoices'],
                       help='Run only selected fetchers')
    
    args = parser.parse_args()
    
    orchestrator = DatabaseFetcherOrchestrator()
    
    if args.fetchers:
        result = orchestrator.run_selected(args.fetchers)
    elif args.mode == 'parallel':
        result = orchestrator.run_all_parallel()
    else:
        result = orchestrator.run_all_sequential()
    
    if result.get("success"):
        print("\n✅ Orchestrator completed successfully")
    else:
        print(f"\n❌ Orchestrator failed: {result.get('message', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()

