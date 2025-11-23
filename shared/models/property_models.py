"""
Real Estate Platform Data Models

Comprehensive models for properties, geofences, price tracking, and compliance.
Designed for the Indian real estate market.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from decimal import Decimal


class PropertyType(str, Enum):
    """Types of real estate properties"""
    APARTMENT = "apartment"
    VILLA = "villa"
    INDEPENDENT_HOUSE = "independent_house"
    PLOT = "plot"
    COMMERCIAL = "commercial"
    OFFICE_SPACE = "office_space"
    RETAIL = "retail"
    INDUSTRIAL = "industrial"
    AGRICULTURAL = "agricultural"


class ComplianceStatus(str, Enum):
    """Compliance/approval status"""
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"
    EXPIRED = "expired"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class DataSource(str, Enum):
    """Property listing data sources"""
    NINETY_NINE_ACRES = "99acres"
    MAGICBRICKS = "magicbricks"
    HOUSING_COM = "housing.com"
    NOBROKER = "nobroker"
    RERA_PORTAL = "rera"
    MANUAL_ENTRY = "manual"
    NEWS_ARTICLE = "news"
    GOVERNMENT_DATA = "government"


class TrendType(str, Enum):
    """Price trend direction"""
    APPRECIATING = "appreciating"
    STABLE = "stable"
    DEPRECIATING = "depreciating"
    VOLATILE = "volatile"


# ============================================================================
# Core Property Model
# ============================================================================

class Property(BaseModel):
    """
    Comprehensive property entity model.
    Supports residential, commercial, and land properties.
    """
    # Unique Identifiers
    property_id: str = Field(..., description="Unique identifier (hash-based)")
    external_id: Optional[str] = Field(None, description="Source platform ID (e.g., 99acres listing ID)")
    
    # Basic Information
    title: str = Field(..., max_length=500)
    description: str = Field(..., description="Full property description")
    
    # Location Details
    address: str
    locality: str = Field(..., description="Locality/Area name (e.g., 'Banjara Hills')")
    city: str
    state: str
    pincode: str
    country: str = "India"
    
    # Geolocation
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    geofence_ids: List[str] = Field(default_factory=list, description="Geofences containing this property")
    
    # Property Specifications
    property_type: PropertyType
    bhk: Optional[int] = Field(None, ge=1, le=20, description="Bedrooms (for residential)")
    bathrooms: Optional[int] = Field(None, ge=1, le=20)
    area_sqft: float = Field(..., gt=0, description="Total area in square feet")
    area_unit: str = Field(default="sqft", description="sqft, sqmt, acres, etc.")
    carpet_area_sqft: Optional[float] = Field(None, description="Usable carpet area")
    
    # Building Details
    floors_total: Optional[int] = None
    floor_number: Optional[int] = None
    age_years: Optional[int] = Field(None, ge=0, description="Age of property in years")
    furnishing: Optional[str] = Field(None, description="Furnished, Semi-furnished, Unfurnished")
    parking: Optional[int] = Field(None, ge=0, description="Number of parking spaces")
    
    # Pricing
    price_inr: float = Field(..., gt=0, description="Total price in Indian Rupees")
    price_per_sqft: float = Field(..., gt=0)
    negotiable: bool = Field(default=True)
    maintenance_monthly: Optional[float] = Field(None, description="Monthly maintenance in INR")
    
    # Builder/Developer Information
    developer_name: Optional[str] = None
    developer_id: Optional[str] = None
    project_name: Optional[str] = None
    builder_reputation_score: Optional[float] = Field(None, ge=0, le=10)
    
    # Compliance & Legal
    rera_id: Optional[str] = Field(None, description="RERA registration number")
    rera_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    rera_expiry_date: Optional[datetime] = None
    
    hmda_approved: Optional[bool] = None
    hmda_approval_number: Optional[str] = None
    
    dtcp_approved: Optional[bool] = None
    dtcp_approval_number: Optional[str] = None
    
    title_clear: Optional[bool] = Field(None, description="Clear property title")
    encumbrance_free: Optional[bool] = None
    
    # Amenities
    amenities: List[str] = Field(default_factory=list, description="List of amenities")
    
    # Possession & Availability
    possession_status: Optional[str] = Field(None, description="Ready to move, Under construction, etc.")
    possession_date: Optional[datetime] = None
    available_from: Optional[datetime] = None
    
    # Listing Metadata
    source: DataSource
    source_url: Optional[str] = None
    listing_date: datetime
    last_updated: datetime
    is_active: bool = Field(default=True)
    views_count: Optional[int] = Field(None, ge=0)
    
    # AI-Generated Insights
    ai_confidence_score: Optional[float] = Field(None, ge=0, le=1, description="AI extraction confidence")
    risk_flags: List[str] = Field(default_factory=list, description="Identified risk factors")
    investment_score: Optional[float] = Field(None, ge=0, le=10)
    
    @validator('price_per_sqft', always=True)
    def calculate_price_per_sqft(cls, v, values):
        """Auto-calculate price per sqft if not provided"""
        if v == 0 and 'price_inr' in values and 'area_sqft' in values:
            return values['price_inr'] / values['area_sqft']
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "property_id": "prop_hyd_ban_001",
                "title": "3BHK Luxury Apartment in Banjara Hills",
                "description": "Spacious 3BHK with modern amenities...",
                "locality": "Banjara Hills",
                "city": "Hyderabad",
                "state": "Telangana",
                "pincode": "500034",
                "latitude": 17.4239,
                "longitude": 78.4738,
                "property_type": "apartment",
                "bhk": 3,
                "area_sqft": 2000,
                "price_inr": 15000000,
                "price_per_sqft": 7500,
                "rera_id": "P02400003456",
                "rera_status": "approved",
                "source": "99acres",
                "listing_date": "2024-01-15T10:00:00Z"
            }
        }


# ============================================================================
# Geofence Model
# ============================================================================

class Geofence(BaseModel):
    """
    Geographic boundary with market intelligence.
    Stores polygon boundaries and aggregate price metrics.
    """
    geofence_id: str = Field(..., description="Unique geofence identifier")
    name: str = Field(..., description="Human-readable name (e.g., 'Banjara Hills, Hyderabad')")
    description: Optional[str] = None
    
    # Geographic Boundary (GeoJSON format)
    boundary: Dict[str, Any] = Field(
        ...,
        description="GeoJSON Polygon or MultiPolygon defining the boundary"
    )
    
    # Hierarchy
    city: str
    state: str
    country: str = "India"
    tier: int = Field(..., ge=1, le=3, description="City tier classification")
    
    # Market Intelligence (Aggregate Metrics)
    avg_price_per_sqft: Optional[float] = Field(None, description="Average price/sqft in this geofence")
    median_price_per_sqft: Optional[float] = None
    price_range_min: Optional[float] = None
    price_range_max: Optional[float] = None
    total_properties: int = Field(default=0, ge=0)
    total_active_listings: int = Field(default=0, ge=0)
    
    # Trend Data
    price_trend_30d: Optional[float] = Field(None, description="% price change in 30 days")
    price_trend_90d: Optional[float] = None
    price_trend_1y: Optional[float] = None
    trend_direction: Optional[TrendType] = None
    
    # Demand Indicators
    avg_days_on_market: Optional[int] = None
    listing_velocity: Optional[float] = Field(None, description="New listings per month")
    
    # Infrastructure & Amenities
    nearby_landmarks: List[str] = Field(default_factory=list)
    connectivity_score: Optional[float] = Field(None, ge=0, le=10)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Price History Model (Time-Series)
# ============================================================================

class PriceHistory(BaseModel):
    """
    Time-series record of property price changes.
    Designed for TimescaleDB hypertable.
    """
    property_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Price Data
    price_inr: float
    price_per_sqft: float
    
    # Change Tracking
    change_inr: Optional[float] = Field(None, description="Absolute price change from previous record")
    change_percent: Optional[float] = Field(None, description="% change from previous record")
    
    # Source
    source: DataSource
    source_url: Optional[str] = None
    
    # Context
    reason: Optional[str] = Field(None, description="Reason for price change if known")


# ============================================================================
# Compliance Record
# ============================================================================

class ComplianceRecord(BaseModel):
    """
    Detailed compliance and regulatory information.
    Applies to both properties and developers.
    """
    entity_id: str = Field(..., description="Property ID or Developer ID")
    entity_type: str = Field(..., description="'property' or 'developer'")
    
    # RERA (Real Estate Regulatory Authority)
    rera_id: Optional[str] = None
    rera_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    rera_registration_date: Optional[datetime] = None
    rera_expiry_date: Optional[datetime] = None
    rera_project_type: Optional[str] = None
    rera_state: Optional[str] = None
    
    # HMDA (Hyderabad Metropolitan Development Authority)
    hmda_approved: Optional[bool] = None
    hmda_approval_number: Optional[str] = None
    hmda_approval_date: Optional[datetime] = None
    hmda_layout_plan_url: Optional[str] = None
    
    # DTCP (Directorate of Town and Country Planning)
    dtcp_approved: Optional[bool] = None
    dtcp_approval_number: Optional[str] = None
    dtcp_approval_date: Optional[datetime] = None
    
    # Legal Clearances
    title_clear: Optional[bool] = None
    encumbrance_certificate: Optional[bool] = None
    occupancy_certificate: Optional[bool] = None
    completion_certificate: Optional[bool] = None
    
    # Environmental Clearances
    environmental_clearance: Optional[bool] = None
    pollution_control_clearance: Optional[bool] = None
    
    # Compliance Score (AI-generated)
    compliance_score: Optional[float] = Field(None, ge=0, le=10)
    risk_level: Optional[str] = Field(None, description="low, medium, high, critical")
    risk_factors: List[str] = Field(default_factory=list)
    
    # Verification
    last_verified: datetime = Field(default_factory=datetime.utcnow)
    verification_source: str
    verified_by: Optional[str] = Field(None, description="System or user who verified")
    
    # Notes
    notes: Optional[str] = None


# ============================================================================
# Developer/Builder Model
# ============================================================================

class Developer(BaseModel):
    """Builder/Developer entity"""
    developer_id: str
    name: str
    legal_name: Optional[str] = None
    
    # Contact
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    
    # Registration
    rera_id: Optional[str] = None
    cin_number: Optional[str] = Field(None, description="Corporate Identification Number")
    
    # Track Record
    total_projects: int = Field(default=0, ge=0)
    completed_projects: int = Field(default=0, ge=0)
    ongoing_projects: int = Field(default=0, ge=0)
    avg_delivery_delay_months: Optional[int] = None
    
    # Reputation
    reputation_score: Optional[float] = Field(None, ge=0, le=10)
    compliance_score: Optional[float] = Field(None, ge=0, le=10)
    customer_rating: Optional[float] = Field(None, ge=0, le=5)
    
    # Financial
    estimated_net_worth_cr: Optional[float] = Field(None, description="Net worth in crores")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Market Trend Analysis
# ============================================================================

class TrendAnalysis(BaseModel):
    """AI-generated market trend analysis"""
    geofence_id: str
    analysis_date: datetime = Field(default_factory=datetime.utcnow)
    
    # Trend Assessment
    trend_direction: TrendType
    confidence: float = Field(..., ge=0, le=1)
    
    # Metrics
    annual_appreciation_rate: Optional[float] = Field(None, description="% per year")
    volatility_score: Optional[float] = Field(None, ge=0, le=10)
    
    # Insights
    key_factors: List[str] = Field(default_factory=list, description="Factors driving the trend")
    summary: str = Field(..., description="2-3 sentence summary")
    
    # Predictions
    predicted_price_6m: Optional[float] = None
    predicted_price_1y: Optional[float] = None
    prediction_confidence: Optional[float] = Field(None, ge=0, le=1)
    
    # LLM Metadata
    llm_model_used: str = "gpt-4-turbo-preview"
    reasoning: str = Field(..., description="Chain-of-thought reasoning")
