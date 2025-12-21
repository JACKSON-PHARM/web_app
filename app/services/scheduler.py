"""
Scheduled Refresh Service
Handles automatic data refresh at intervals
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable
from app.config import settings

logger = logging.getLogger(__name__)

class RefreshScheduler:
    """Manages scheduled data refresh"""
    
    def __init__(self, refresh_callback: Callable):
        self.refresh_callback = refresh_callback
        self.is_running = False
        self.last_refresh: Optional[datetime] = None
        self.next_refresh: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None
        self.interval_minutes = settings.AUTO_REFRESH_INTERVAL_MINUTES
        self.enabled = settings.AUTO_REFRESH_ENABLED
    
    async def start(self):
        """Start the scheduler"""
        if not self.enabled:
            logger.info("Auto-refresh is disabled")
            return
        
        if self.is_running:
            logger.warning("Scheduler already running")
            return
        
        self.is_running = True
        logger.info(f"🔄 Starting refresh scheduler (interval: {self.interval_minutes} minutes)")
        
        # Schedule first refresh
        self._schedule_next_refresh()
        
        # Start the loop
        self._task = asyncio.create_task(self._refresh_loop())
    
    async def stop(self):
        """Stop the scheduler"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ Refresh scheduler stopped")
    
    def _schedule_next_refresh(self):
        """Schedule the next refresh time"""
        if self.last_refresh:
            self.next_refresh = self.last_refresh + timedelta(minutes=self.interval_minutes)
        else:
            self.next_refresh = datetime.now() + timedelta(minutes=self.interval_minutes)
    
    async def _refresh_loop(self):
        """Main refresh loop"""
        while self.is_running:
            try:
                now = datetime.now()
                
                # Check if it's time to refresh
                if self.next_refresh and now >= self.next_refresh:
                    logger.info("🔄 Starting scheduled data refresh...")
                    self.last_refresh = datetime.now()
                    
                    # Run refresh callback
                    try:
                        await self.refresh_callback()
                        logger.info("✅ Scheduled refresh completed")
                    except Exception as e:
                        logger.error(f"❌ Scheduled refresh failed: {e}")
                    
                    # Schedule next refresh
                    self._schedule_next_refresh()
                    logger.info(f"📅 Next refresh scheduled: {self.next_refresh}")
                
                # Sleep for 1 minute and check again
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in refresh loop: {e}")
                await asyncio.sleep(60)
    
    def trigger_manual_refresh(self):
        """Trigger an immediate refresh"""
        logger.info("🔄 Manual refresh triggered")
        self.last_refresh = datetime.now()
        self._schedule_next_refresh()
        return asyncio.create_task(self.refresh_callback())
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            'enabled': self.enabled,
            'is_running': self.is_running,
            'interval_minutes': self.interval_minutes,
            'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None,
            'next_refresh': self.next_refresh.isoformat() if self.next_refresh else None
        }
    
    def update_interval(self, minutes: int):
        """Update refresh interval"""
        self.interval_minutes = minutes
        if self.is_running:
            self._schedule_next_refresh()
        logger.info(f"⏰ Refresh interval updated to {minutes} minutes")

