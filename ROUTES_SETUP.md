# 🚌 Route Configuration Setup Guide

This guide explains how to set up and load the 112 bus routes into your database with the new pricing system.

## What Was Updated

### 1. **Database Schema Changes**
   - Added `price` field to the `routes` table (Decimal with 2 decimal places)
   - Added `distance_km` field to the `routes` table (optional, stores route distance)

### 2. **Route Model Updates** (`app/models/route.py`)
   - Added `price: Decimal` field
   - Added `distance_km: float | None` field

### 3. **API Schema Updates** (`app/schemas/route.py`)
   - Updated `RouteCreate` to require `price` and optional `distance_km`
   - Updated `RouteUpdate` to allow updating `price` and `distance_km`
   - Updated `RouteOut` to include price and distance in responses

### 4. **Service Updates** (`app/services/route_service.py`)
   - Updated `create_route()` to handle price and distance_km
   - Updated `update_route()` to allow price/distance updates

## Pricing System

The pricing is calculated based on distance:
- **Shortest route (3.8 km)**: ₹15.00
- **Longest route (52 km)**: ₹24.40 (approximately)
- **Interpolated pricing**: All routes between min/max distance are priced proportionally

This allows admins to easily update prices later via the API.

## Setup Steps

### Step 1: Run Database Migration

Apply the migration to add the new columns:

```bash
make migrate
```

Or manually:

```bash
alembic upgrade head
```

### Step 2: Load Routes into Database

Run the route loading script:

```bash
python scripts/load_routes.py
```

This script will:
- ✅ Parse all 112 routes with their origin, destination, and distance
- ✅ Calculate prices based on distance (starting at ₹15 for shortest)
- ✅ Insert all routes into the database
- ✅ Display a summary of inserted routes

**Expected output:**
```
Distance range: 3.8 km - 52.0 km
Price range: 15.00 - 24.40
✅ Successfully inserted 112 routes!

Sample routes:
  Route 001: Megenagna → Kara (7.7 km) - Price: 15.34
  Route 002: Kore Mekanisa → Merkato (11.1 km) - Price: 15.84
  ...
```

## API Usage

### Create a New Route

```bash
curl -X POST http://localhost:8000/api/v1/routes \
  -H "Content-Type: application/json" \
  -d '{
    "routeCode": "NEW001",
    "routeName": "New Route Name",
    "price": 20.50,
    "distanceKm": 15.5
  }'
```

### Get All Routes

```bash
curl http://localhost:8000/api/v1/routes
```

Response includes price:
```json
{
  "routes": [
    {
      "id": "...",
      "routeCode": "001",
      "routeName": "Megenagna → Kara",
      "price": 15.34,
      "distanceKm": 7.7,
      "status": "ACTIVE",
      "isDeleted": false,
      "createdAt": "2026-05-17T10:00:00Z",
      "updatedAt": "2026-05-17T10:00:00Z"
    }
  ]
}
```

### Update Route Price

```bash
curl -X PATCH http://localhost:8000/api/v1/routes/{routeId} \
  -H "Content-Type: application/json" \
  -d '{
    "price": 18.00
  }'
```

## 112 Routes Configured

All routes include:
- ✅ Route number (001-112)
- ✅ Origin and destination stops
- ✅ Distance in kilometers
- ✅ Calculated price (admins can update)

### Route Examples:

| Route | From | To | Distance | Price |
|-------|------|-----|----------|-------|
| 001 | Megenagna | Kara | 7.7 km | ₹15.34 |
| 072 | Hanamariam | Saris Abo | 3.8 km | ₹15.00 |
| 091 | Merkato | Teji | 52.0 km | ₹24.40 |
| 112 | Circular Route | Ring Road | - | ₹15.00 |

## Troubleshooting

### "Route code already exists"
Routes were already loaded. Clear the database first:
```bash
python -c "from app.db.session import SessionLocal; from sqlalchemy import text; db=SessionLocal(); db.execute(text('DELETE FROM routes')); db.commit()"
```

Then run the script again.

### Database connection error
Ensure your `.env` file has the correct `DATABASE_URL`:
```bash
echo $DATABASE_URL
```

Should output something like:
```
postgresql://user:password@localhost:5432/movemate_db
```

### Migration conflicts
If migrations fail, check the current state:
```bash
make current
make history
```

## Next Steps

1. ✅ Run migration: `make migrate`
2. ✅ Load routes: `python scripts/load_routes.py`
3. ✅ Test API: `curl http://localhost:8000/api/v1/routes`
4. 📋 Update stops and assign to routes (separate step)
5. 🚌 Assign buses to routes

---

**Notes:**
- Prices can be updated by admins via the PATCH endpoint
- Distances are stored for reference and fare calculations
- Route codes are formatted as 3-digit numbers (001-112)
