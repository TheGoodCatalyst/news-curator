"""
99acres.com Property Scraper

Scrapes property listings from 99acres.com (India's leading real estate portal).
Handles pagination, anti-bot measures, and data normalization.
"""
import asyncio
import hashlib
import re
from typing import List, Optional, Dict
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
import json

from shared.models import Property, PropertyType, DataSource, ComplianceStatus
from shared.utils import get_logger, log_with_context
from shared.config import settings

logger = get_logger("99acres-scraper")


class NinetyNineAcresScraper:
    """
    Scrapes property listings from 99acres.com
    
    Features:
    - JavaScript-rendering support (Playwright)
    - Anti-bot evasion (delays, user agents)
    - Pagination handling
    - Data normalization
    """
    
    BASE_URL = "https://www.99acres.com"
    
    def __init__(self):
        """Initialize scraper with Playwright"""
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
    async def init_browser(self):
        """Initialize headless browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        # Create context with realistic user agent
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        self.page = await context.new_page()
        logger.info("Browser initialized")
    
    async def close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")
    
    def _build_search_url(
        self,
        city: str,
        property_type: str = "residential",
        bhk: Optional[int] = None,
        budget_min: Optional[int] = None,
        budget_max: Optional[int] = None
    ) -> str:
        """
        Build search URL for 99acres
        
        Args:
            city: City name (e.g., 'hyderabad', 'bangalore')
            property_type: 'residential' or 'commercial'
            bhk: Number of bedrooms
            budget_min: Min budget in lakhs
            budget_max: Max budget in lakhs
        
        Returns:
            Search URL
        """
        # Example URL format: https://www.99acres.com/property-in-hyderabad-ffid
        base_search = f"{self.BASE_URL}/property-in-{city.lower()}"
        
        # Add property type filter
        if property_type == "residential":
            base_search += "-ffid"
        
        # Add filters as query params
        params = []
        if bhk:
            params.append(f"bedroom={bhk}")
        if budget_min:
            params.append(f"budget_min={budget_min}")
        if budget_max:
            params.append(f"budget_max={budget_max}")
        
        if params:
            base_search += "?" + "&".join(params)
        
        return base_search
    
    async def scrape_listing_page(self, url: str) -> List[Dict]:
        """
        Scrape a single listing page
        
        Args:
            url: URL to scrape
        
        Returns:
            List of raw property data dicts
        """
        try:
            log_with_context(logger, "info", f"Scraping page: {url}", url=url)
            
            # Navigate to page
            await self.page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for listings to load
            await self.page.wait_for_selector('.srpTuple', timeout=10000)
            
            # Add random delay (anti-bot)
            await asyncio.sleep(2 + (hash(url) % 3))
            
            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find all property cards
            property_cards = soup.find_all('div', class_='srpTuple')
            
            properties = []
            for card in property_cards:
                try:
                    property_data = self._extract_property_from_card(card)
                    if property_data:
                        properties.append(property_data)
                except Exception as e:
                    logger.warning(f"Failed to extract property from card: {e}")
                    continue
            
            log_with_context(
                logger, "info",
                f"Extracted {len(properties)} properties from page",
                count=len(properties)
            )
            
            return properties
        
        except Exception as e:
            logger.error(f"Failed to scrape page {url}: {e}")
            return []
    
    def _extract_property_from_card(self, card) -> Optional[Dict]:
        """
        Extract property data from a single card element
        
        Args:
            card: BeautifulSoup element
        
        Returns:
            Raw property data dict
        """
        try:
            # Extract title
            title_elem = card.find('h2', class_='srpTuple__propertyHeading')
            title = title_elem.text.strip() if title_elem else "Untitled Property"
            
            # Extract price
            price_elem = card.find('span', class_='srpTuple__price')
            price_text = price_elem.text.strip() if price_elem else "0"
            price_inr = self._parse_price(price_text)
            
            # Extract area
            area_elem = card.find('span', class_='srpTuple__area')
            area_text = area_elem.text.strip() if area_elem else "0 sq.ft."
            area_sqft = self._parse_area(area_text)
            
            # Extract location
            location_elem = card.find('span', class_='srpTuple__locationName')
            locality = location_elem.text.strip() if location_elem else "Unknown"
            
            # Extract BHK
            bhk_match= re.search(r'(\d+)\s*BHK', title, re.IGNORECASE)
            bhk = int(bhk_match.group(1)) if bhk_match else None
            
            # Extract property type
            property_type = PropertyType.APARTMENT  # Default
            if 'villa' in title.lower():
                property_type = PropertyType.VILLA
            elif 'plot' in title.lower() or 'land' in title.lower():
                property_type = PropertyType.PLOT
            elif 'house' in title.lower():
                property_type = PropertyType.INDEPENDENT_HOUSE
            
            # Extract URL
            link_elem = card.find('a', href=True)
            source_url = self.BASE_URL + link_elem['href'] if link_elem else None
            
            # Extract RERA ID if mentioned
            rera_elem = card.find(string=re.compile(r'RERA', re.IGNORECASE))
            rera_id = None
            if rera_elem:
                rera_match = re.search(r'RERA[:\s]*([A-Z0-9]+)', rera_elem, re.IGNORECASE)
                rera_id = rera_match.group(1) if rera_match else None
            
            # Generate property ID (hash of URL or title)
            property_id = hashlib.md5(
                (source_url or title).encode()
            ).hexdigest()[:16]
            
            return {
                "property_id": f"99ac_{property_id}",
                "title": title,
                "locality": locality,
                "price_inr": price_inr,
                "area_sqft": area_sqft,
                "price_per_sqft": price_inr / area_sqft if area_sqft > 0 else 0,
                "bhk": bhk,
                "property_type": property_type,
                "source": DataSource.NINETY_NINE_ACRES,
                "source_url": source_url,
                "rera_id": rera_id,
                "rera_status": ComplianceStatus.APPROVED if rera_id else ComplianceStatus.UNKNOWN,
                "listing_date": datetime.utcnow()
            }
        
        except Exception as e:
            logger.warning(f"Failed to parse property card: {e}")
            return None
    
    def _parse_price(self, price_text: str) -> float:
        """
        Parse price string to INR float
        
        Examples:
            "₹ 1.5 Cr" -> 15000000
            "₹ 85 Lac" -> 8500000
            "₹ 45000 per sq.ft." -> 0 (we'll calculate separately)
        """
        try:
            # Remove currency symbols and extra spaces
            price_text = price_text.replace('₹', '').replace(',', '').strip()
            
            # Handle Crore (Cr)
            if 'cr' in price_text.lower():
                value = float(re.search(r'([\d.]+)', price_text).group(1))
                return value * 10000000  # 1 Cr = 10 million
            
            # Handle Lakh/Lac
            if 'lac' in price_text.lower() or 'lakh' in price_text.lower():
                value = float(re.search(r'([\d.]+)', price_text).group(1))
                return value * 100000  # 1 Lakh = 100k
            
            # Handle thousand (K)
            if 'k' in price_text.lower():
                value = float(re.search(r'([\d.]+)', price_text).group(1))
                return value * 1000
            
            # Direct number
            return float(re.search(r'([\d.]+)', price_text).group(1))
        
        except Exception as e:
            logger.warning(f"Failed to parse price '{price_text}': {e}")
            return 0
    
    def _parse_area(self, area_text: str) -> float:
        """
        Parse area string to square feet
        
        Examples:
            "2000 sq.ft." -> 2000
            "1800 sqft" -> 1800
            "200 sq.m." -> 2152 (converted)
        """
        try:
            # Extract number
            area_match = re.search(r'([\d,]+)', area_text.replace(',', ''))
            if not area_match:
                return 0
            
            area_value = float(area_match.group(1))
            
            # Check unit
            if 'sq.m' in area_text.lower() or 'sqm' in area_text.lower():
                # Convert sq.m to sq.ft (1 sqm = 10.764 sqft)
                return area_value * 10.764
            
            # Default is sq.ft
            return area_value
        
        except Exception as e:
            logger.warning(f"Failed to parse area '{area_text}': {e}")
            return 0
    
    async def scrape_city(
        self,
        city: str,
        property_type: str = "residential",
        max_pages: int = 5
    ) -> List[Property]:
        """
        Scrape properties for a city
        
        Args:
            city: City name
            property_type: Property type filter
            max_pages: Maximum pages to scrape
        
        Returns:
            List of Property objects
        """
        await self.init_browser()
        
        all_properties = []
        
        try:
            # Build initial search URL
            search_url = self._build_search_url(city, property_type)
            
            for page_num in range(1, max_pages + 1):
                # Construct page URL
                page_url = f"{search_url}&page={page_num}" if page_num > 1 else search_url
                
                # Scrape page
                raw_properties = await self.scrape_listing_page(page_url)
                
                # Convert to Property objects
                for raw_prop in raw_properties:
                    try:
                        # Add missing fields with defaults
                        raw_prop.update({
                            "description": raw_prop.get("title", ""),
                            "address": f"{raw_prop.get('locality', '')}, {city}",
                            "city": city,
                            "state": "Unknown",  # TODO: City to state mapping
                            "pincode": "000000",  # TODO: Geocoding
                            "latitude": 0.0,  # TODO: Geocoding
                            "longitude": 0.0,  # TODO: Geocoding
                            "last_updated": datetime.utcnow()
                        })
                        
                        property_obj = Property(**raw_prop)
                        all_properties.append(property_obj)
                    except Exception as e:
                        logger.warning(f"Failed to create Property object: {e}")
                        continue
                
                log_with_context(
                    logger, "info",
                    f"Scraped page {page_num}/{max_pages}",
                    page=page_num,
                    properties=len(raw_properties)
                )
                
                # Rate limiting
                await asyncio.sleep(3)
        
        finally:
            await self.close_browser()
        
        log_with_context(
            logger, "info",
            f"Scraping complete for {city}",
            city=city,
            total_properties=len(all_properties)
        )
        
        return all_properties


# Example usage
async def main():
    scraper = NinetyNineAcresScraper()
    properties = await scraper.scrape_city("hyderabad", max_pages=2)
    
    print(f"\n=== Scraped {len(properties)} properties ===")
    for prop in properties[:5]:  # Show first 5
        print(f"\n{prop.title}")
        print(f"  Location: {prop.locality}, {prop.city}")
        print(f"  Price: ₹{prop.price_inr:,.0f} ({prop.bhk} BHK)")
        print(f"  Area: {prop.area_sqft} sqft @ ₹{prop.price_per_sqft:,.0f}/sqft")
        if prop.rera_id:
            print(f"  RERA: {prop.rera_id}")


if __name__ == "__main__":
    asyncio.run(main())
