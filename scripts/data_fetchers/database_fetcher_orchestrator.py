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
from scripts.data_fetchers.database_grn_fetcher import DatabaseGRNFetcher
from scripts.data_fetchers.database_orders_fetcher import DatabaseOrdersFetcher
from scripts.data_fetchers.database_supplier_invoices_fetcher import DatabaseSupplierInvoicesFetcher


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
            fetcher = DatabaseStockFetcher(self.app_root)
            result = fetcher.run()
            self.results['stock'] = result
            return result
        except Exception as e:
            error_result = {"success": False, "message": str(e)}
            self.results['stock'] = error_result
            return error_result
    
    def run_grn_fetcher(self) -> Dict:
        """Run GRN fetcher"""
        self._update_progress("Starting GRN Download...", 0.2)
        try:
            fetcher = DatabaseGRNFetcher(self.app_root)
            result = fetcher.run()
            self.results['grn'] = result
            return result
        except Exception as e:
            error_result = {"success": False, "message": str(e)}
            self.results['grn'] = error_result
            return error_result
    
    def run_orders_fetcher(self) -> Dict:
        """Run orders fetcher"""
        self._update_progress("Starting Orders Download...", 0.4)
        try:
            fetcher = DatabaseOrdersFetcher(self.app_root)
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
            fetcher = DatabaseSupplierInvoicesFetcher(self.app_root)
            result = fetcher.run()
            self.results['supplier_invoices'] = result
            return result
        except Exception as e:
            error_result = {"success": False, "message": str(e)}
            self.results['supplier_invoices'] = error_result
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
            self._update_progress(f"✅ Stock: {stock_result.get('total_updated', 0)} records", 0.25)
            
            grn_result = self.run_grn_fetcher()
            self._update_progress(f"✅ GRN: {grn_result.get('total_grns', 0)} GRNs", 0.5)
            
            orders_result = self.run_orders_fetcher()
            self._update_progress(f"✅ Orders: {orders_result.get('total_orders', 0)} orders", 0.75)
            
            supplier_result = self.run_supplier_invoices_fetcher()
            self._update_progress(f"✅ Supplier Invoices: {supplier_result.get('total_invoices', 0)} invoices", 0.9)
            
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
                    "grn": grn_result,
                    "orders": orders_result,
                    "supplier_invoices": supplier_result
                },
                "summary": {
                    "stock_records": stock_result.get('total_updated', 0),
                    "grn_count": grn_result.get('total_grns', 0),
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
        Run all fetchers in parallel (where possible)
        Note: Some fetchers may need to run sequentially due to API rate limits
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
            
            # Validate prerequisites
            if not self.base_fetcher.validate_prerequisites():
                return {"success": False, "message": "No companies configured"}
            
            # Run fetchers in parallel using threads
            threads = []
            results = {}
            
            def run_with_result(fetcher_name, fetcher_func):
                try:
                    result = fetcher_func()
                    results[fetcher_name] = result
                except Exception as e:
                    results[fetcher_name] = {"success": False, "message": str(e)}
            
            # Start all fetchers
            t1 = threading.Thread(target=run_with_result, args=("stock", self.run_stock_fetcher))
            t2 = threading.Thread(target=run_with_result, args=("grn", self.run_grn_fetcher))
            t3 = threading.Thread(target=run_with_result, args=("orders", self.run_orders_fetcher))
            t4 = threading.Thread(target=run_with_result, args=("supplier_invoices", self.run_supplier_invoices_fetcher))
            
            threads = [t1, t2, t3, t4]
            
            for t in threads:
                t.start()
            
            # Wait for all to complete
            for t in threads:
                t.join()
            
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
                    "grn_count": results.get("grn", {}).get('total_grns', 0),
                    "purchase_orders": results.get("orders", {}).get('total_purchase_orders', 0),
                    "branch_orders": results.get("orders", {}).get('total_branch_orders', 0),
                    "supplier_invoices": results.get("supplier_invoices", {}).get('total_invoices', 0)
                }
            }
            
            self._update_progress("=" * 70)
            self._update_progress("🎉 ALL FETCHERS COMPLETED!")
            self._update_progress("=" * 70)
            self._update_progress(f"⏱️  Total Time: {duration}", 1.0)
            
            return summary
            
        except Exception as e:
            error_msg = f"Orchestrator error: {str(e)}"
            self._update_progress(f"❌ {error_msg}")
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
                'grn': self.run_grn_fetcher,
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
                       choices=['stock', 'grn', 'orders', 'supplier_invoices'],
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

