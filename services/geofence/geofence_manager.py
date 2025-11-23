"""
Geofence Manager Service

Manages geographic boundaries (geofences) and property-to-geofence matching using PostGIS.
Calculates aggregate market metrics per geofence.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import json

from shared.models import Geofence, Property, TrendType
from shared.config import settings
from shared.utils import get_logger, log_with_context

logger = get_logger("geofence-manager")


class GeofenceManager:
    """
    Manages geofences and property matching using PostGIS.
    
    Features:
    - Create/update geofence polygons
    - Match properties to geofences (ST_Contains queries)
    - Calculate aggregate metrics (avg price, trends)
    - Identify price anomalies
    """
    
    def __init__(self):
        """Initialize database connection"""
        self.conn = psycopg2.connect(settings.postgres_url)
        self._ensure_postgis_extension()
        self._create_tables()
    
    def _ensure_postgis_extension(self):
        """Enable PostGIS extension if not already enabled"""
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            self.conn.commit()
            logger.info("PostGIS extension enabled")
    
    def _create_tables(self):
        """Create geofences and properties tables with geometry columns"""
        with self.conn.cursor() as cur:
            # Geofences table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS geofences (
                    geofence_id VARCHAR(100) PRIMARY KEY,
                    name VARCHAR(500) NOT NULL,
                    description TEXT,
                    city VARCHAR(100),
                    state VARCHAR(100),
                    country VARCHAR(100) DEFAULT 'India',
                    tier INTEGER,
                    
                    -- Geometry column (PostGIS)
                    boundary GEOMETRY(POLYGON, 4326),
                    
                    -- Market metrics
                    avg_price_per_sqft DECIMAL,
                    median_price_per_sqft DECIMAL,
                    price_range_min DECIMAL,
                    price_range_max DECIMAL,
                    total_properties INTEGER DEFAULT 0,
                    total_active_listings INTEGER DEFAULT 0,
                    
                    -- Trends
                    price_trend_30d DECIMAL,
                    price_trend_90d DECIMAL,
                    price_trend_1y DECIMAL,
                    trend_direction VARCHAR(50),
                    
                    -- Metadata
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_updated TIMESTAMP DEFAULT NOW()
                );
                
                -- Spatial index on boundary
                CREATE INDEX IF NOT EXISTS idx_geofences_boundary 
                ON geofences USING GIST(boundary);
            """)
            
            # Properties table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS properties (
                    property_id VARCHAR(100) PRIMARY KEY,
                    title VARCHAR(500),
                    description TEXT,
                    
                    -- Location
                    address TEXT,
                    locality VARCHAR(200),
                    city VARCHAR(100),
                    state VARCHAR(100),
                    pincode VARCHAR(20),
                    
                    -- Geometry (Point)
                    location GEOMETRY(POINT, 4326),
                    
                    -- Property details
                    property_type VARCHAR(50),
                    bhk INTEGER,
                    area_sqft DECIMAL,
                    price_inr DECIMAL,
                    price_per_sqft DECIMAL,
                    
                    -- Compliance
                    rera_id VARCHAR(100),
                    rera_status VARCHAR(50),
                    hmda_approved BOOLEAN,
                    dtcp_approved BOOLEAN,
                    
                    -- Metadata
                    source VARCHAR(50),
                    source_url TEXT,
                    listing_date TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
                );
                
                -- Spatial index on location
                CREATE INDEX IF NOT EXISTS idx_properties_location 
                ON properties USING GIST(location);
                
                -- Index on city for faster queries
                CREATE INDEX IF NOT EXISTS idx_properties_city 
                ON properties(city);
            """)
            
            # Property-Geofence mapping table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS property_geofence_mapping (
                    property_id VARCHAR(100),
                    geofence_id VARCHAR(100),
                    matched_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (property_id, geofence_id),
                    FOREIGN KEY (property_id) REFERENCES properties(property_id) ON DELETE CASCADE,
                    FOREIGN KEY (geofence_id) REFERENCES geofences(geofence_id) ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_mapping_geofence 
                ON property_geofence_mapping(geofence_id);
            """)
            
            self.conn.commit()
            logger.info("Database tables created/verified")
    
    def create_geofence(self, geofence: Geofence) -> bool:
        """
        Create a new geofence with polygon boundary.
        
        Args:
            geofence: Geofence object with boundary (GeoJSON)
        
        Returns:
            Success boolean
        """
        try:
            # Convert GeoJSON to WKT (Well-Known Text) for PostGIS
            geojson_str = json.dumps(geofence.boundary)
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO geofences (
                        geofence_id, name, description, city, state, country, tier,
                        boundary, avg_price_per_sqft, total_properties
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        ST_GeomFromGeoJSON(%s), %s, %s
                    )
                    ON CONFLICT (geofence_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        boundary = EXCLUDED.boundary,
                        last_updated = NOW()
                """, (
                    geofence.geofence_id,
                    geofence.name,
                    geofence.description,
                    geofence.city,
                    geofence.state,
                    geofence.country,
                    geofence.tier,
                    geojson_str,
                    geofence.avg_price_per_sqft,
                    geofence.total_properties
                ))
                
                self.conn.commit()
                
                log_with_context(
                    logger, "info",
                    "Geofence created/updated",
                    geofence_id=geofence.geofence_id,
                    name=geofence.name
                )
                
                return True
        
        except Exception as e:
            logger.error(f"Failed to create geofence: {e}")
            self.conn.rollback()
            return False
    
    def insert_property(self, property: Property) -> bool:
        """
        Insert property with geolocation.
        
        Args:
            property: Property object
        
        Returns:
            Success boolean
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO properties (
                        property_id, title, description, address, locality, city, state, pincode,
                        location, property_type, bhk, area_sqft, price_inr, price_per_sqft,
                        rera_id, rera_status, hmda_approved, dtcp_approved,
                        source, source_url, listing_date, last_updated, is_active
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (property_id) DO UPDATE SET
                        price_inr = EXCLUDED.price_inr,
                        price_per_sqft = EXCLUDED.price_per_sqft,
                        last_updated = NOW(),
                        is_active = EXCLUDED.is_active
                """, (
                    property.property_id, property.title, property.description,
                    property.address, property.locality, property.city, property.state, property.pincode,
                    property.longitude, property.latitude,
                    property.property_type.value, property.bhk, property.area_sqft,
                    property.price_inr, property.price_per_sqft,
                    property.rera_id, property.rera_status.value,
                    property.hmda_approved, property.dtcp_approved,
                    property.source.value, property.source_url,
                    property.listing_date, property.last_updated, property.is_active
                ))
                
                self.conn.commit()
                return True
        
        except Exception as e:
            logger.error(f"Failed to insert property: {e}")
            self.conn.rollback()
            return False
    
    def match_property_to_geofences(self, property_id: str) -> List[str]:
        """
        Find all geofences that contain a property.
        
        Uses PostGIS ST_Contains for spatial query.
        
        Args:
            property_id: Property ID
        
        Returns:
            List of geofence IDs
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT g.geofence_id, g.name
                    FROM geofences g
                    CROSS JOIN properties p
                    WHERE p.property_id = %s
                      AND ST_Contains(g.boundary, p.location)
                """, (property_id,))
                
                results = cur.fetchall()
                geofence_ids = [r['geofence_id'] for r in results]
                
                # Update mapping table
                if geofence_ids:
                    cur.execute("""
                        INSERT INTO property_geofence_mapping (property_id, geofence_id)
                        VALUES (%s, unnest(%s::varchar[]))
                        ON CONFLICT DO NOTHING
                    """, (property_id, geofence_ids))
                    
                    self.conn.commit()
                
                log_with_context(
                    logger, "info",
                    f"Property matched to {len(geofence_ids)} geofences",
                    property_id=property_id,
                    geofence_count=len(geofence_ids)
                )
                
                return geofence_ids
        
        except Exception as e:
            logger.error(f"Failed to match property to geofences: {e}")
            return []
    
    def calculate_geofence_metrics(self, geofence_id: str) -> Dict:
        """
        Calculate aggregate metrics for a geofence.
        
        Args:
            geofence_id: Geofence ID
        
        Returns:
            Dict with metrics
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_properties,
                        COUNT(*) FILTER (WHERE is_active = TRUE) as active_listings,
                        AVG(price_per_sqft) as avg_price_per_sqft,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_sqft) as median_price_per_sqft,
                        MIN(price_per_sqft) as price_range_min,
                        MAX(price_per_sqft) as price_range_max,
                        STDDEV(price_per_sqft) as price_stddev
                    FROM properties p
                    JOIN property_geofence_mapping m ON p.property_id = m.property_id
                    WHERE m.geofence_id = %s
                """, (geofence_id,))
                
                metrics = cur.fetchone()
                
                # Update geofence table
                cur.execute("""
                    UPDATE geofences SET
                        total_properties = %s,
                        total_active_listings = %s,
                        avg_price_per_sqft = %s,
                        median_price_per_sqft = %s,
                        price_range_min = %s,
                        price_range_max = %s,
                        last_updated = NOW()
                    WHERE geofence_id = %s
                """, (
                    metrics['total_properties'],
                    metrics['active_listings'],
                    metrics['avg_price_per_sqft'],
                    metrics['median_price_per_sqft'],
                    metrics['price_range_min'],
                    metrics['price_range_max'],
                    geofence_id
                ))
                
                self.conn.commit()
                
                log_with_context(
                    logger, "info",
                    "Geofence metrics calculated",
                    geofence_id=geofence_id,
                    total_properties=metrics['total_properties'],
                    avg_price=float(metrics['avg_price_per_sqft']) if metrics['avg_price_per_sqft'] else 0
                )
                
                return dict(metrics)
        
        except Exception as e:
            logger.error(f"Failed to calculate geofence metrics: {e}")
            return {}
    
    def find_undervalued_properties(self, geofence_id: str, std_dev_threshold: float = 1.0) -> List[Dict]:
        """
        Find properties priced below average in a geofence.
        
        Args:
            geofence_id: Geofence ID
            std_dev_threshold: How many standard deviations below mean
        
        Returns:
            List of undervalued properties
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    WITH stats AS (
                        SELECT 
                            AVG(price_per_sqft) as avg_price,
                            STDDEV(price_per_sqft) as stddev_price
                        FROM properties p
                        JOIN property_geofence_mapping m ON p.property_id = m.property_id
                        WHERE m.geofence_id = %s AND p.is_active = TRUE
                    )
                    SELECT 
                        p.property_id,
                        p.title,
                        p.price_inr,
                        p.price_per_sqft,
                        p.locality,
                        (stats.avg_price - p.price_per_sqft) / stats.stddev_price as z_score
                    FROM properties p
                    JOIN property_geofence_mapping m ON p.property_id = m.property_id
                    CROSS JOIN stats
                    WHERE m.geofence_id = %s 
                      AND p.is_active = TRUE
                      AND p.price_per_sqft < (stats.avg_price - %s * stats.stddev_price)
                    ORDER BY z_score DESC
                    LIMIT 20
                """, (geofence_id, geofence_id, std_dev_threshold))
                
                return cur.fetchall()
        
        except Exception as e:
            logger.error(f"Failed to find undervalued properties: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


# Example usage
if __name__ == "__main__":
    from shared.models import PropertyType
    
    manager = GeofenceManager()
    
    # Create a sample geofence for Banjara Hills, Hyderabad
    geofence = Geofence(
        geofence_id="hyd_banjara_hills",
        name="Banjara Hills, Hyderabad",
        description="Premium residential area in Hyderabad",
        city="Hyderabad",
        state="Telangana",
        tier=1,
        boundary={
            "type": "Polygon",
            "coordinates": [[
                [78.4418, 17.4239],  # Southwest corner
                [78.4638, 17.4239],  # Southeast corner
                [78.4638, 17.4439],  # Northeast corner
                [78.4418, 17.4439],  # Northwest corner
                [78.4418, 17.4239]   # Close polygon
            ]]
        }
    )
    
    success = manager.create_geofence(geofence)
    print(f"Geofence created: {success}")
    
    manager.close()
