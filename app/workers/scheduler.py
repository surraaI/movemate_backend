from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.repositories.gps_tracking_repository import GPSTrackingRepository
from app.services.eta_service import ETAService
import logging

try:  # pragma: no cover - optional dependency
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:  # pragma: no cover - fallback when APScheduler is unavailable
    class BackgroundScheduler:  # type: ignore[too-many-ancestors]
        def __init__(self, *args, **kwargs):
            self._started = False

        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            self._started = True

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_bus_arrivals():
    """
    Check all active trips and calculate ETAs for their destinations
    """
    logger.info("Checking ETA for all active trips...")
    try:
        db = SessionLocal()
        repo = GPSTrackingRepository(db)
        eta_service = ETAService(db)
        
        active_buses = repo.list_live_fleet()
        logger.info(f"Found {len(active_buses)} active buses")
        
        for bus in active_buses:
            try:
                eta = eta_service.predict_trip_eta(bus.trip_id)
                logger.info(
                    f"Trip {eta.trip_id} on route {eta.route_id}: "
                    f"ETA to {eta.destination_stop_name} is {eta.eta_minutes} minutes "
                    f"(arrival at {eta.estimated_arrival})"
                )
            except Exception as e:
                logger.warning(f"Failed to calculate ETA for trip {bus.trip_id}: {e}")
        
        db.close()
        logger.info("ETA check complete")
    except Exception as e:
        logger.error(f"Error during ETA check: {e}", exc_info=True)

scheduler.add_job(check_bus_arrivals, "interval", seconds=30)

def start_scheduler():
    scheduler.start()
    logger.info("Scheduler started")