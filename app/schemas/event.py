from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    event_type: str
    user_id: Optional[str] = None
    route_id: Optional[str] = None
    trip_id: Optional[str] = None
    event_metadata: Optional[str] = None
    occurred_at: datetime
    created_at: datetime


class ActivityTrendOut(BaseModel):
    """Aggregated activity metrics over a time period."""
    period_start: datetime
    period_end: datetime
    granularity: str  # "hour", "day", "week"
    total_events: int
    events_by_type: dict[str, int]
    unique_users: int
    unique_routes: int
    payment_success_count: int
    payment_failed_count: int
    tickets_issued: int
    trips_started: int
    trips_completed: int
