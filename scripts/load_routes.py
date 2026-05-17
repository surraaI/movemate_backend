"""
Script to insert routes into the database with calculated pricing.
Pricing starts at 15 for the shortest distance and increases proportionally.
"""

import sys
from decimal import Decimal
from pathlib import Path

# Add parent directory to path to import app module
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.models.route import Route
from app.core.config import settings

# Route data: (route_no, origin, through, destination, distance_km)
ROUTES_DATA = [
    (1, "Megenagna", "Gurd Shola", "Kara", 7.7),
    (2, "Kore Mekanisa", "Lideta", "Merkato", 11.1),
    (3, "Ayertena", "Mexico", "Minilik Square", 10.8),
    (4, "Kaliti", "Kira", "Merkato", 19.4),
    (5, "Kore Mekanisa", "Bisrategebreil", "Minilik Square", 12.7),
    (6, "Kera", "Shebel", "Semen Addisu Gebeya", 9.9),
    (7, "Megenagna", "Kotebe", "Aleltu", 49.0),
    (8, "Kechene", "Yohannes", "Merkato", 9.4),
    (9, "Birass Cilinic Bole School", "Kasanchiz", "Piazza", 10.5),
    (10, "Kotebe Teachers Collage", "Kebena", "Piazza", 12.7),
    (11, "Kolfe", "Atkilt tera", "Minilik Hospital", 10.0),
    (12, "Gurara", "Afncho ber", "Merkato", 9.9),
    (13, "Italy Embassy", "Sinima Ethipia", "Merkato", 9.9),
    (14, "Saris Abo", "Gandi", "Minilik Square", 12.3),
    (15, "Megenagna", "Abuare", "Merkato", 10.5),
    (16, "Kidanemihret", "Afnch Ber", "Merkato", 7.9),
    (17, "kusquam", "kidste Mariam", "Merkato", 9.1),
    (18, "keraniyo", "kolfe Dildy", "Merkato", 7.3),
    (19, "Asko", "Pawlos", "Piazza", 12.3),
    (20, "Dile Ber", "Enkulal Fabrica", "Merkato", 8.6),
    (21, "Flidoro", "kolfe Dildy", "Merkato", 8.6),
    (22, "Summit/codominium/", "22 mazoria", "Legehar", 12.3),
    (23, "Lamberet", "Afnch Ber", "Merkato", 12.4),
    (24, "Dire Sololia", "Pawlos", "Merkato", 15.9),
    (25, "Legehar", "Gotera", "Akaki", 19.0),
    (26, "Merkato", "Coca Coal", "Sebeta", 25.5),
    (27, "Legehar", "Gotera", "Kaliti", 14.9),
    (28, "Asko Sansuzi", "Mesalemia", "Merkato", 11.1),
    (29, "Addisu Sefer", "Teklehaimanot", "Merkato", 12.7),
    (30, "Sululta", "Semen Gegeya", "Merkato", 25.5),
    (31, "Legehar", "4 kilo", "Shiromeda", 7.4),
    (32, "Hana Mariyame Kotebe", "22 Mazoria", "Legehar", 10.6),
    (33, "Kotebe Gebiriel", "Kebena", "4 Kilo", 11.4),
    (34, "Germen Square", "Kera", "Merkato", 9.8),
    (35, "Lebu Musica bet", "Lafto", "Merkato", 15.0),
    (36, "Kara Kore", "Torhailoch", "Legehar", 11.7),
    (37, "Keraniyo", "Mexico", "Mimilik Square", 12.0),
    (38, "Lebu Musica Bete", "Minilik Square", "6 Kilo", 11.0),
    (39, "Bole School Medhanialem", "Kazanchiz", "Merkato", 9.6),
    (40, "Kara Alo", "4 kilo", "Merkato", 17.9),
    (41, "Eyesus Church", "4 kilo", "Merkato", 8.5),
    (42, "Megenagna", "Bole", "Bole Legehare", 9.8),
    (43, "Megenesha", "Mesalemia", "Merkato", 30.2),
    (44, "Legedadi", "4 kilo", "Merkato", 30.4),
    (45, "Legehar", "Piazza", "Dilbere", 8.6),
    (46, "Gergi", "22 mazoria", "4 Kilo", 11.2),
    (47, "Yenegew Fire School", "Mechael", "Merkato", 6.0),
    (48, "Bole Mikhael Square", "Gandi Hospital", "Minilk Sqare", 10.9),
    (49, "Ayat Condominium", "C.M.C", "Megenagna", 8.8),
    (50, "Ayeretena", "Torhailoch", "Megenagna", 12.1),
    (51, "Betel Hosipital", "Zenbwork", "Merkato", 10.9),
    (52, "Gergi", "Bole", "Merkato", 14.1),
    (53, "Bole Michael", "Meskel square", "Shiromeda", 11.5),
    (54, "Lafeto", "Kera", "Leghar", 9.5),
    (55, "Legehar", "4 kilo", "Gurara", 9.5),
    (56, "Saris Abo", "Meskel Square", "Shiromeda", 14.2),
    (57, "Kara", "22 Mazoria", "Leghar", 14.4),
    (58, "Alem Bank", "Torhailoch", "Leghar", 12.0),
    (59, "Betel Hospital", "Coca Cola", "Mililik Sqare", 11.5),
    (60, "Deber Zeit", "Gotera", "Leghar", 47.2),
    (61, "Ayat Condominium", "22 Mazoria", "Leghar Through Kasanchis", 15.8),
    (62, "Sebeta", "Torhailoch", "Leghar", 23.8),
    (63, "Merkato", "Atena Tera", "Mikililand/Birechko fabrica", 9.1),
    (64, "6 Kilo", "Kazanchiz", "Megenagna Gorfe Aswegaj", 9.5),
    (65, "Merkato", "Coca cola", "Alem Bank", 11.0),
    (66, "Merkato", "coca cola", "Karakore", 10.5),
    (67, "Mekanisa Jemo", "mexico", "Legehar", 10.2),
    (68, "Torhailoche", "Gibi Gebriel", "Minlik Hospital", 10.2),
    (69, "Philpos Church", "Mesalemia", "Merkato", 5.9),
    (70, "Kasanchis", "Mexico", "Ayertena", 11.0),
    (71, "Gerji", "Bole Tenatabia", "Balcha Hospital", 11.0),
    (72, "Hanamariam", "58 kebele", "Saris Abo", 3.8),
    (73, "Legehar", "Torhailoch", "Wingate School", 10.2),
    (74, "C.M.C Michael", "Tikur Anbessa", "Merkato", 13.3),
    (75, "6 Kilo", "Kazanchiz", "Kera", 10.4),
    (76, "Megenagna", "Zerihun bulding", "Kaliti", 18.4),
    (77, "Ayertena", "Sar bet", "Kera", 13.0),
    (78, "Megenagna", "Bherawi", "Gofa Condo", 12.4),
    (79, "4 Kilo", "Signal", "Summit", 12.7),
    (80, "Semen Gebeya", "Kazanchiz", "Megenagna", 12.4),
    (81, "6 Kilo", "Yohannes", "Asko", 13.0),
    (82, "Sefera Goro", "24 kebele", "Balcha Hospital", 14.6),
    (83, "Ayat Condominium", "kebena", "6 Kilo", 18.0),
    (84, "Kolfe", "Amanuel", "Legehar", 9.5),
    (85, "Merkato", "18 Mazoria", "Holeta", 45.0),
    (86, "Ayertena", "Mebrat Hail", "Korki Fabrica", 12.3),
    (87, "Wingate college", "Ketena 2", "Ayertena", 10.5),
    (88, "Merkato", "Piazza", "Chancho", 40.0),
    (89, "Merkato", "4 Kilo", "Sendafa", 44.0),
    (90, "Betel Hospital", "Torhailoch", "Legehar", 10.0),
    (91, "Merkato", "Torhailoch", "Teji", 52.0),
    (92, "Hanamariam", "Sar bet", "Balcha Hospital", 9.6),
    (93, "Bole Bulbula", "Bole Airport", "Megenagna", 15.2),
    (94, "Piazza", "Pawlos", "Mekililand Birchko Fabrica", 9.9),
    (95, "Merkato", "Fil Doro", "Addisalem", 47.0),
    (96, "Megenagna", "Anbessa Gerag", "Goro Sefera", 7.0),
    (97, "Megenagna", "Ayat", "Legetafo", 15.8),
    (98, "Dukem", "Gelan", "Saris Abo", 26.3),
    (99, "Ayertena", "Welete", "Alemgena", 8.3),
    (100, "Jemo Site", "Dese Hotel", "Merkato", 14.5),
    (101, "Megenagna", "Ayat", "Yeka Ayat Con.1sq", 12.0),
    (102, "Legehar", "Magenagna", "Karalo", 13.7),
    (103, "Jemo", "Mexico", "Piazza", 12.2),
    (104, "Kera", "wehalimat", "Worku Sefer", 12.0),
    (105, "Lagehar", "Holand Embasy", "Anfo meda", 12.0),
    (106, "Megenagna", "C.M.C.", "Goro", 10.8),
    (107, "Saris Abo", "Kality", "Akaki korkoro Fabrica", 11.4),
    (108, "Minilik square", "18 Mazoria", "Asco Addisu Sefer", 9.3),
    (109, "Saris Abo", "Kaliti", "tulu dimtu", 12.0),
    (110, "Akaki", "Meskel Square", "6 kilo", 24.9),
    (111, "Piazza", "Medhanialm school", "Burayu", 16.6),
    (112, "Circular Route", "Ring Road", "Ring Road", 0.0),  # Circular route has no specific distance
]


def calculate_price(distance_km: float, min_distance: float, max_distance: float, 
                   min_price: Decimal, max_price: Decimal) -> Decimal:
    """Calculate price based on distance using linear interpolation."""
    if distance_km == 0:  # Circular route
        return min_price
    
    if max_distance == 0:
        return min_price
    
    # Linear interpolation
    if distance_km <= min_distance:
        return min_price
    
    ratio = (distance_km - min_distance) / (max_distance - min_distance)
    price_range = max_price - min_price
    # Convert ratio to Decimal for proper calculation
    price = min_price + (Decimal(str(ratio)) * price_range)
    return Decimal(str(round(float(price), 2)))


def main():
    # Connect to database
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get distance stats
        distances = [d for _, _, _, _, d in ROUTES_DATA if d > 0]
        min_distance = min(distances)
        max_distance = max(distances)
        
        print(f"Distance range: {min_distance} km - {max_distance} km")
        
        # Pricing tiers
        min_price = Decimal("15.00")
        # Calculate max price: roughly 1 per 5km
        max_price = min_price + Decimal(str(max_distance / 5))
        
        print(f"Price range: {min_price} - {max_price}")
        
        # Check for existing routes
        existing_count = session.query(Route).count()
        if existing_count > 0:
            print(f"⚠️  Database already contains {existing_count} routes. Clearing...")
            session.query(Route).delete()
            session.commit()
        
        # Insert routes
        created_routes = []
        for route_no, origin, through, destination, distance_km in ROUTES_DATA:
            # Calculate price
            price = calculate_price(distance_km, min_distance, max_distance, min_price, max_price)
            
            # Create route code and name
            route_code = str(route_no).zfill(3)
            route_name = f"{origin} → {destination}"
            
            route = Route(
                route_code=route_code,
                route_name=route_name,
                price=price,
                distance_km=distance_km if distance_km > 0 else None,
            )
            session.add(route)
            created_routes.append((route_no, route_code, route_name, distance_km, price))
        
        session.commit()
        
        print(f"\n✅ Successfully inserted {len(created_routes)} routes!")
        print("\nSample routes:")
        for route_no, code, name, distance, price in created_routes[:5]:
            print(f"  Route {code}: {name} ({distance} km) - Price: {price}")
        
        print("\nLongest routes:")
        sorted_routes = sorted(created_routes, key=lambda x: x[3] if x[3] else 0, reverse=True)
        for route_no, code, name, distance, price in sorted_routes[:5]:
            print(f"  Route {code}: {name} ({distance} km) - Price: {price}")
        
        print("\nShortest routes:")
        sorted_routes = sorted(created_routes, key=lambda x: x[3] if x[3] else float('inf'))
        for route_no, code, name, distance, price in sorted_routes[:5]:
            if distance and distance > 0:
                print(f"  Route {code}: {name} ({distance} km) - Price: {price}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
