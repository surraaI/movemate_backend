CREATE TABLE IF NOT EXISTS trip_logs (
    id VARCHAR(36) PRIMARY KEY,
    trip_id VARCHAR(36) NOT NULL REFERENCES active_trips(trip_id) ON DELETE CASCADE,
    bus_id VARCHAR(36) NOT NULL REFERENCES buses(bus_id) ON DELETE RESTRICT,
    route_id VARCHAR(36) NOT NULL REFERENCES routes(id) ON DELETE RESTRICT,
    driver_id VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    timestamp TIMESTAMPTZ NOT NULL,
    day_of_week INTEGER NOT NULL,
    time_range VARCHAR(32) NOT NULL,
    month INTEGER NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    speed DOUBLE PRECISION,
    mileage_covered DOUBLE PRECISION NOT NULL DEFAULT 0,
    passenger_count INTEGER NOT NULL DEFAULT 0,
    stop_id VARCHAR(36),
    total_time_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    congestion_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    high_demand_segment SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trip_logs_trip_id_timestamp ON trip_logs (trip_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trip_logs_route_id_timestamp ON trip_logs (route_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trip_logs_stop_id_timestamp ON trip_logs (stop_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS reroute_suggestions (
    id VARCHAR(36) PRIMARY KEY,
    trip_id VARCHAR(36) NOT NULL REFERENCES active_trips(trip_id) ON DELETE CASCADE,
    bus_id VARCHAR(36) NOT NULL REFERENCES buses(bus_id) ON DELETE RESTRICT,
    route_id VARCHAR(36) NOT NULL REFERENCES routes(id) ON DELETE RESTRICT,
    suggested_at TIMESTAMPTZ NOT NULL,
    current_segment VARCHAR(255),
    trigger_reason VARCHAR(255) NOT NULL,
    new_route_polyline TEXT NOT NULL,
    estimated_time_saving_minutes DOUBLE PRECISION NOT NULL DEFAULT 0,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    accepted BOOLEAN NOT NULL DEFAULT FALSE,
    feedback_at TIMESTAMPTZ,
    outcome_recorded BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'suggested',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reroute_suggestions_trip_id ON reroute_suggestions (trip_id, suggested_at DESC);

CREATE TABLE IF NOT EXISTS reroute_outcomes (
    id VARCHAR(36) PRIMARY KEY,
    reroute_id VARCHAR(36) NOT NULL REFERENCES reroute_suggestions(id) ON DELETE CASCADE,
    bus_id VARCHAR(36) NOT NULL REFERENCES buses(bus_id) ON DELETE RESTRICT,
    accepted BOOLEAN NOT NULL DEFAULT FALSE,
    actual_time_saving DOUBLE PRECISION NOT NULL DEFAULT 0,
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reroute_outcomes_reroute_id ON reroute_outcomes (reroute_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS retraining_log (
    id VARCHAR(36) PRIMARY KEY,
    rows_used INTEGER NOT NULL,
    accuracy_before DOUBLE PRECISION,
    accuracy_after DOUBLE PRECISION,
    promoted BOOLEAN NOT NULL DEFAULT FALSE,
    model_version VARCHAR(64),
    message TEXT,
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_retraining_log_timestamp ON retraining_log (timestamp DESC);
