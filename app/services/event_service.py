import json
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.models.event import Event, EventType


class EventService:
    """Service for writing events and retrieving activity analytics."""

    @staticmethod
    def write_event(
        db: Session,
        event_type: str,
        user_id: Optional[str] = None,
        route_id: Optional[str] = None,
        trip_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        occurred_at: Optional[datetime] = None,
    ) -> Event:
        """
        Write an event to the events table.
        
        Args:
            db: Database session
            event_type: Type of event (use EventType constants)
            user_id: Optional user ID
            route_id: Optional route ID
            trip_id: Optional trip ID
            metadata: Optional dict of event details (will be JSON serialized)
            occurred_at: Time event occurred (defaults to now)
        
        Returns:
            Event object
        """
        event = Event(
            event_type=event_type,
            user_id=user_id,
            route_id=route_id,
            trip_id=trip_id,
            event_metadata=json.dumps(metadata) if metadata else None,
            occurred_at=occurred_at or datetime.utcnow(),
        )
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def get_activity_trends(
        db: Session,
        from_time: datetime,
        to_time: datetime,
        granularity: str = "day",
    ) -> dict:
        """
        Get aggregated activity metrics over a time period.
        
        Args:
            db: Database session
            from_time: Start of period
            to_time: End of period
            granularity: "hour", "day", or "week"
        
        Returns:
            Dict with trend metrics
        """
        # Filter events in time range
        events_query = db.query(Event).filter(
            Event.occurred_at >= from_time,
            Event.occurred_at <= to_time,
        )

        total_events = events_query.count()
        
        # Events by type
        events_by_type = db.query(
            Event.event_type,
            func.count(Event.id).label("count")
        ).filter(
            Event.occurred_at >= from_time,
            Event.occurred_at <= to_time,
        ).group_by(Event.event_type).all()
        
        events_by_type_dict = {e[0]: int(e[1]) for e in events_by_type}
        
        # Unique users and routes
        unique_users = events_query.filter(Event.user_id.isnot(None)).distinct(Event.user_id).count()
        unique_routes = events_query.filter(Event.route_id.isnot(None)).distinct(Event.route_id).count()
        
        # Specific event counts
        payment_success_count = events_query.filter(Event.event_type == EventType.PAYMENT_SUCCESS).count()
        payment_failed_count = events_query.filter(Event.event_type == EventType.PAYMENT_FAILED).count()
        tickets_issued = events_query.filter(Event.event_type == EventType.TICKET_CREATED).count()
        trips_started = events_query.filter(Event.event_type == EventType.TRIP_START).count()
        trips_completed = events_query.filter(Event.event_type == EventType.TRIP_END).count()

        return {
            "period_start": from_time,
            "period_end": to_time,
            "granularity": granularity,
            "total_events": total_events,
            "events_by_type": events_by_type_dict,
            "unique_users": unique_users,
            "unique_routes": unique_routes,
            "payment_success_count": payment_success_count,
            "payment_failed_count": payment_failed_count,
            "tickets_issued": tickets_issued,
            "trips_started": trips_started,
            "trips_completed": trips_completed,
        }

    @staticmethod
    def get_events(
        db: Session,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        route_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        """
        Retrieve events with optional filters.
        
        Args:
            db: Database session
            event_type: Filter by event type
            user_id: Filter by user ID
            route_id: Filter by route ID
            limit: Number of events to return
            offset: Pagination offset
        
        Returns:
            List of Event objects
        """
        query = db.query(Event)
        
        if event_type:
            query = query.filter(Event.event_type == event_type)
        if user_id:
            query = query.filter(Event.user_id == user_id)
        if route_id:
            query = query.filter(Event.route_id == route_id)
        
        return query.order_by(Event.occurred_at.desc()).limit(limit).offset(offset).all()
