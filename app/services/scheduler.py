"""
Scheduled Refresh Service
Handles automatic data refresh every 60 minutes between 8 AM and 6 PM
"""
import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Optional, Callable
from app.config import settings

logger = logging.getLogger(__name__)

class RefreshScheduler:
    """Manages scheduled data refresh every 60 minutes between 8 AM and 6 PM"""
    
    # Active hours: 8 AM to 6 PM
    START_HOUR = 8  # 8:00 AM
    END_HOUR = 18   # 6:00 PM
    INTERVAL_MINUTES = 60  # Refresh every 60 minutes
    
    def __init__(self, refresh_callback: Callable):
        self.refresh_callback = refresh_callback
        self.is_running = False
        self.last_refresh: Optional[datetime] = None
        self.next_refresh: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None
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
        logger.info(f"🔄 Starting refresh scheduler (every {self.INTERVAL_MINUTES} minutes between {self.START_HOUR}:00 AM and {self.END_HOUR}:00 PM)")
        
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
    
    def _is_within_active_hours(self, dt: datetime) -> bool:
        """Check if datetime is within active hours (8 AM - 6 PM)"""
        hour = dt.hour
        return self.START_HOUR <= hour < self.END_HOUR
    
    def _schedule_next_refresh(self):
        """Schedule the next refresh time (every 60 minutes between 8 AM and 6 PM)"""
        now = datetime.now()
        
        # If we're within active hours, schedule next refresh in 60 minutes
        if self._is_within_active_hours(now):
            self.next_refresh = now + timedelta(minutes=self.INTERVAL_MINUTES)
            
            # If next refresh would be after 6 PM, schedule for 8 AM next day
            if self.next_refresh.hour >= self.END_HOUR:
                next_day = now.date() + timedelta(days=1)
                self.next_refresh = datetime.combine(next_day, time(self.START_HOUR, 0))
                logger.info(f"📅 Next refresh scheduled: {self.next_refresh.strftime('%Y-%m-%d %H:%M:%S')} (after hours, will resume at 8 AM)")
            else:
                logger.info(f"📅 Next refresh scheduled: {self.next_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            # Outside active hours - schedule for 8 AM (today or tomorrow)
            current_hour = now.hour
            
            if current_hour < self.START_HOUR:
                # Before 8 AM today - schedule for 8 AM today
                self.next_refresh = datetime.combine(now.date(), time(self.START_HOUR, 0))
                logger.info(f"📅 Next refresh scheduled: {self.next_refresh.strftime('%Y-%m-%d %H:%M:%S')} (before active hours)")
            else:
                # After 6 PM - schedule for 8 AM tomorrow
                next_day = now.date() + timedelta(days=1)
                self.next_refresh = datetime.combine(next_day, time(self.START_HOUR, 0))
                logger.info(f"📅 Next refresh scheduled: {self.next_refresh.strftime('%Y-%m-%d %H:%M:%S')} (after hours, will resume at 8 AM)")
    
    async def _refresh_loop(self):
        """Main refresh loop - checks every minute for scheduled refresh times"""
        while self.is_running:
            try:
                now = datetime.now()
                
                # Check if it's time to refresh (within 1 minute of scheduled time)
                if self.next_refresh:
                    time_diff = (self.next_refresh - now).total_seconds()
                    
                    # If we're within 60 seconds of the scheduled time, trigger refresh
                    if 0 <= time_diff <= 60:
                        # Only refresh if we're within active hours
                        if self._is_within_active_hours(now):
                            logger.info("=" * 80)
                            logger.info("🔄 SCHEDULED REFRESH TRIGGERED")
                            logger.info(f"   Scheduled time: {self.next_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
                            logger.info(f"   Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                            logger.info("=" * 80)
                            self.last_refresh = datetime.now()
                            
                            # Run refresh callback
                            try:
                                await self.refresh_callback()
                                logger.info("=" * 80)
                                logger.info("✅ SCHEDULED REFRESH COMPLETED")
                                logger.info(f"   Completed at: {datetime.now().isoformat()}")
                                logger.info("=" * 80)
                            except Exception as e:
                                logger.error("=" * 80)
                                logger.error("❌ SCHEDULED REFRESH FAILED")
                                logger.error(f"   Error: {e}")
                                logger.error(f"   Failed at: {datetime.now().isoformat()}")
                                import traceback
                                logger.error(traceback.format_exc())
                                logger.error("=" * 80)
                        else:
                            logger.info(f"⏸️ Skipping refresh - outside active hours (current: {now.strftime('%H:%M')}, active: {self.START_HOUR}:00-{self.END_HOUR}:00)")
                        
                        # Schedule next refresh
                        self._schedule_next_refresh()
                
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
            'active_hours': f"{self.START_HOUR}:00 - {self.END_HOUR}:00",
            'interval_minutes': self.INTERVAL_MINUTES,
            'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None,
            'next_refresh': self.next_refresh.isoformat() if self.next_refresh else None
        }

