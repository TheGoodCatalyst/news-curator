# Real Estate Intelligence Platform

AI-powered real estate intelligence platform for the Indian market with property price tracking, geofencing, compliance monitoring, and market trend analysis.

## 🏠 Features

### 1. **Property Data Ingestion**
- **99acres.com scraper** with anti-bot evasion
- **MagicBricks.com** integration (coming soon)
- Automatic data normalization (prices, areas, locations)
- RERA ID extraction from listings

### 2. **Geofencing & Location Intelligence**
- **PostGIS-powered** spatial queries
- Create custom geographic boundaries
- Automatic property-to-geofence matching
- Aggregate market metrics per geofence
- Identify price anomalies and undervalued properties

### 3. **Price Tracking & Trends**
- Time-series price history
- Trend analysis (appreciation/depreciation)
- Price prediction using AI
- Comparative market analysis

### 4. **Compliance Monitoring**
- **RERA** (Real Estate Regulatory Authority) validation
- **HMDA** (Hyderabad Metropolitan Development Authority) tracking
- **DTCP** (Directorate of Town and Country Planning) verification
- Builder/developer compliance scoring
- Legal clearance monitoring

### 5. **AI-Powered Insights**
- LLM-based property analysis
- Market trend interpretation
- Developer reputation analysis
- Risk assessment

---

## 📊 Architecture

Adapts the News Curator event-driven architecture for real estate:

```
Data Sources (99acres, RERA, etc.)
    ↓
Ingestion Service (Playwright scrapers)
    ↓
Kafka Message Bus
    ↓
Real Estate Processor (AI analysis)
    ↓
Storage Layer:
    - PostgreSQL + PostGIS (properties & geofences)
    - TimescaleDB (price history)
    - Neo4j (relationships)
    - Redis (cache)
    ↓
API Gateway
    ↓
User Applications
```

---

## 🗺️ Data Models

### Property
- **Location**: Address, lat/lng, geofence membership
- **Details**: Type, BHK, area, price, amenities
- **Compliance**: RERA, HMDA, DTCP status
- **Developer**: Builder info, reputation score

### Geofence
- **Boundary**: GeoJSON polygon
- **Metrics**: Avg price, trends, inventory
- **Market Intel**: Appreciation rates, demand indicators

### Price History (Time-Series)
- Historical price points
- Change tracking
- Trend detection

### Compliance Record
- RERA registration details
- HMDA/DTCP approvals
- Legal clearances
- Risk scoring

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- PostgreSQL with PostGIS
- Python 3.11+
- OpenAI API key

### Setup

1. **Install dependencies**:
```bash
pip install playwright psycopg2-binary
playwright install chromium
```

2. **Start infrastructure**:
```bash
# PostGIS included in docker-compose
docker-compose up -d postgres
```

3. **Run 99acres scraper**:
```bash
cd services/real-estate-ingestion/scrapers
python ninety_nine_acres_scraper.py
```

4. **Test geofencing**:
```bash
cd services/geofence
python geofence_manager.py
```

---

## 📍 Geofencing Example

```python
from services.geofence.geofence_manager import GeofenceManager
from shared.models import Geofence

manager = GeofenceManager()

# Create geofence for Banjara Hills
geofence = Geofence(
    geofence_id="hyd_banjara_hills",
    name="Banjara Hills, Hyderabad",
    city="Hyderabad",
    state="Telangana",
    tier=1,
    boundary={
        "type": "Polygon",
        "coordinates": [[[78.44, 17.42], [78.46, 17.42], ...]]
    }
)

manager.create_geofence(geofence)

# Match properties to geofence
geofence_ids = manager.match_property_to_geofences("property_123")

# Calculate market metrics
metrics = manager.calculate_geofence_metrics("hyd_banjara_hills")
print(f"Avg Price: ₹{metrics['avg_price_per_sqft']}/sqft")

# Find undervalued properties
deals = manager.find_undervalued_properties("hyd_banjara_hills")
```

---

## 🔍 Data Sources

### Listing Marketplaces
| Source | Status | API | Strategy |
|--------|--------|-----|----------|
| **99acres.com** | ✅ Implemented | No | Playwright scraper |
| **MagicBricks.com** | 🚧 Planned | No | Playwright scraper |
| **Housing.com** | 📋 Backlog | Partial | Hybrid |

### Regulatory Bodies

#### RERA (State-wise)
- **Telangana**: https://rera.telangana.gov.in/
- **Tamil Nadu**: https://www.tnrera.in/
- **Maharashtra**: https://maharera.mahaonline.gov.in/
- **Karnataka**: https://rera.karnataka.gov.in/

**Integration**: Web scraping + manual verification

#### HMDA (Hyderabad)
- Website: https://hmda.gov.in/
- **Approved Layouts**: PDF parsing + manual entry

#### DTCP (State-wise)
- Varies by state
- **Integration**: Manual monitoring + structured data entry

### Government Data
- **Card Values**: Registration department data
- **Market Prices**: Government valuation reports

---

## 🎯 Use Cases

### 1. Property Discovery
```
Find all 3BHK apartments in Banjara Hills
under ₹2 Crores with RERA approval
```

### 2. Price Alerts
```
Alert me when:
- New property listed in my geofence
- Price drops > 10%
- Property below market average
```

### 3. Investment Analysis
```
Show me:
- Top appreciating localities
- Undervalued properties
- High-compliance builders
```

### 4. Compliance Check
```
Verify:
- RERA registration status
- HMDA approval
- Builder track record
```

---

## 🗄️ Database Schema

### PostGIS Tables

**properties**:
- `location` GEOMETRY(POINT, 4326) -- Lat/lng
- Spatial index on location

**geofences**:
- `boundary` GEOMETRY(POLYGON, 4326) -- Geofence polygon
- Spatial index on boundary

**property_geofence_mapping**:
- Links properties to containing geofences

### Spatial Queries

```sql
-- Find properties in a geofence
SELECT * FROM properties p
JOIN geofences g ON ST_Contains(g.boundary, p.location)
WHERE g.geofence_id = 'hyd_banjara_hills';

-- Calculate avg price per geofence
SELECT 
    g.name,
    AVG(p.price_per_sqft) as avg_price,
    COUNT(*) as property_count
FROM geofences g
JOIN properties p ON ST_Contains(g.boundary, p.location)
GROUP BY g.geofence_id;
```

---

## 🤖 AI Features

### Property Insight Generator
```python
# LLM analyzes property and generates insights
insights = processor.analyze_property(property)
# Returns: Investment score, risk factors, price justification
```

### Market Trend Analysis
```python
# AI interprets price trends
analysis = processor.analyze_market_trend(geofence_id)
# Returns: Trend direction, key factors, predictions
```

### Compliance Risk Scoring
```python
# AI assesses compliance risk
risk = processor.assess_compliance_risk(property, compliance_record)
# Returns: Risk score, concerns, recommendations
```

---

## 🔐 Compliance Features

### RERA Validation
- Verify registration number
- Check expiry date
- Validate project type
- Track approval status

### Builder Due Diligence
- Project delivery history
- Compliance track record
- Customer ratings
- Financial health indicators

### Legal Clearances
- Title verification
- Encumbrance certificate
- Occupancy certificate
- Completion certificate

---

## 📈 Price Tracking

### Time-Series Storage
Using TimescaleDB for efficient time-series queries:

```sql
-- Create hypertable for price history
SELECT create_hypertable('price_history', 'timestamp');

-- Query price changes over time
SELECT 
    time_bucket('1 week', timestamp) as week,
    AVG(price_per_sqft) as avg_price
FROM price_history
WHERE property_id = 'prop_123'
GROUP BY week
ORDER BY week;
```

### Trend Detection
Algorithms:
- **Linear regression** for trend direction
- **Seasonal decomposition** for patterns
- **Anomaly detection** for sudden spikes

---

## 🎯 Roadmap

### Phase 1 (Current)
- [x] Data models
- [x] 99acres scraper
- [x] PostGIS geofencing
- [ ] Price tracking
- [ ] Basic API

### Phase 2 (Next 4 weeks)
- [ ] MagicBricks scraper
- [ ] RERA data integration
- [ ] AI-powered insights
- [ ] Alert system

### Phase 3 (Future)
- [ ] Mobile app
- [ ] Vector search for similar properties
- [ ] Prediction models
- [ ] Chatbot interface

---

## 🛠️ Development

### Project Structure
```
news-curator/
├── services/
│   ├── real-estate-ingestion/
│   │   └── scrapers/
│   │       └── ninety_nine_acres_scraper.py
│   ├── geofence/
│   │   └── geofence_manager.py
│   └── real-estate-processor/  (coming soon)
├── shared/
│   └── models/
│       └── property_models.py
└── README_REAL_ESTATE.md
```

### Testing Scrapers

```bash
# Test 99acres scraper
python services/real-estate-ingestion/scrapers/ninety_nine_acres_scraper.py

# Output: Scraped properties with RERA IDs, prices, locations
```

### Testing Geofencing

```bash
# Test geofence creation and matching
python services/geofence/geofence_manager.py
```

---

## 📚 References

### Indian Real Estate Regulations
- [RERA Act 2016](https://rera.gov.in/)
- [HMDA Guidelines](https://hmda.gov.in/)
- [DTCP Regulations](varies by state)

### Geospatial Standards
- [GeoJSON Specification](https://geojson.org/)
- [PostGIS Documentation](https://postgis.net/docs/)

---

## 🤝 Contributing

This is a reference implementation demonstrating event-driven architecture for real estate intelligence. Contributions welcome!

---

**Built with ❤️ for the Indian Real Estate Market**
