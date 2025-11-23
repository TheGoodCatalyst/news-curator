"""
RSS Feed Configuration Manager

Manages custom RSS/XML feed sources for both news and real estate content.
Supports adding, listing, and validating feed sources.
"""
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Dict, Optional
from enum import Enum
import json


class FeedCategory(str, Enum):
    """Feed content categories"""
    GENERAL_NEWS = "general_news"
    REAL_ESTATE = "real_estate"
    FINANCE = "finance"
    TECHNOLOGY = "technology"
    REGULATORY = "regulatory"
    INDUSTRY = "industry"
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    HOUSING_FINANCE = "housing_finance"
    INFRASTRUCTURE = "infrastructure"


class FeedSource(BaseModel):
    """RSS/XML feed source configuration"""
    feed_id: str = Field(..., description="Unique identifier for the feed")
    name: str = Field(..., description="Human-readable name")
    url: HttpUrl = Field(..., description="RSS/XML feed URL")
    category: FeedCategory
    
    # Polling configuration
    poll_interval_minutes: int = Field(default=30, ge=5, le=1440, description="How often to poll")
    enabled: bool = Field(default=True)
    
    # Feed metadata
    publisher: Optional[str] = None
    language: str = Field(default="en")
    country: str = Field(default="IN")
    
    # Parsing hints
    extract_images: bool = Field(default=True)
    extract_authors: bool = Field(default=True)
    
    # Metadata
    added_date: str
    last_fetched: Optional[str] = None
    article_count: int = Field(default=0, ge=0)


class FeedRegistry:
    """
    Registry for managing RSS feed sources.
    Supports adding custom feeds and pre-configured sources.
    """
    
    # Pre-configured Economic Times Realty feeds
    ECONOMIC_TIMES_REALTY_FEEDS = [
        {
            "feed_id": "et_realty_recent",
            "name": "Economic Times Realty - Recent Stories",
            "url": "https://realty.economictimes.indiatimes.com/rss/recentstories",
            "category": FeedCategory.REAL_ESTATE,
            "publisher": "Economic Times",
            "poll_interval_minutes": 30
        },
        {
            "feed_id": "et_realty_regulatory",
            "name": "Economic Times Realty - Regulatory",
            "url": "https://realty.economictimes.indiatimes.com/rss/regulatory",
            "category": FeedCategory.REGULATORY,
            "publisher": "Economic Times",
            "poll_interval_minutes": 60
        },
        {
            "feed_id": "et_realty_industry",
            "name": "Economic Times Realty - Industry",
            "url": "https://realty.economictimes.indiatimes.com/rss/industry",
            "category": FeedCategory.INDUSTRY,
            "publisher": "Economic Times",
            "poll_interval_minutes": 30
        },
        {
            "feed_id": "et_realty_residential",
            "name": "Economic Times Realty - Residential",
            "url": "https://realty.economictimes.indiatimes.com/rss/residential",
            "category": FeedCategory.RESIDENTIAL,
            "publisher": "Economic Times",
            "poll_interval_minutes": 45
        },
        {
            "feed_id": "et_realty_housing_finance",
            "name": "Economic Times Realty - Housing Finance",
            "url": "https://realty.economictimes.indiatimes.com/rss/housing-finance",
            "category": FeedCategory.HOUSING_FINANCE,
            "publisher": "Economic Times",
            "poll_interval_minutes": 60
        },
        {
            "feed_id": "et_realty_infrastructure",
            "name": "Economic Times Realty - Infrastructure",
            "url": "https://realty.economictimes.indiatimes.com/rss/infrastructure",
            "category": FeedCategory.INFRASTRUCTURE,
            "publisher": "Economic Times",
            "poll_interval_minutes": 60
        }
    ]
    
    def __init__(self, config_file: str = "feed_sources.json"):
        """Initialize registry from config file"""
        self.config_file = config_file
        self.feeds: Dict[str, FeedSource] = {}
        self._load_feeds()
    
    def _load_feeds(self):
        """Load feeds from config file"""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                for feed_data in data.get("feeds", []):
                    feed = FeedSource(**feed_data)
                    self.feeds[feed.feed_id] = feed
        except FileNotFoundError:
            # Initialize with default feeds
            self._load_default_feeds()
            self._save_feeds()
    
    def _load_default_feeds(self):
        """Load pre-configured Economic Times feeds"""
        from datetime import datetime
        
        for feed_config in self.ECONOMIC_TIMES_REALTY_FEEDS:
            feed_config["added_date"] = datetime.utcnow().isoformat()
            feed = FeedSource(**feed_config)
            self.feeds[feed.feed_id] = feed
    
    def _save_feeds(self):
        """Save feeds to config file"""
        data = {
            "feeds": [feed.model_dump(mode='json') for feed in self.feeds.values()]
        }
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_feed(self, feed: FeedSource) -> bool:
        """
        Add a new custom feed source.
        
        Args:
            feed: FeedSource object
        
        Returns:
            Success boolean
        """
        if feed.feed_id in self.feeds:
            print(f"Feed {feed.feed_id} already exists. Use update_feed() instead.")
            return False
        
        self.feeds[feed.feed_id] = feed
        self._save_feeds()
        print(f"✅ Added feed: {feed.name}")
        return True
    
    def remove_feed(self, feed_id: str) -> bool:
        """Remove a feed source"""
        if feed_id not in self.feeds:
            print(f"Feed {feed_id} not found")
            return False
        
        del self.feeds[feed_id]
        self._save_feeds()
        print(f"🗑️  Removed feed: {feed_id}")
        return True
    
    def update_feed(self, feed_id: str, **kwargs) -> bool:
        """Update feed properties"""
        if feed_id not in self.feeds:
            print(f"Feed {feed_id} not found")
            return False
        
        feed = self.feeds[feed_id]
        for key, value in kwargs.items():
            if hasattr(feed, key):
                setattr(feed, key, value)
        
        self._save_feeds()
        print(f"✏️  Updated feed: {feed_id}")
        return True
    
    def get_feed(self, feed_id: str) -> Optional[FeedSource]:
        """Get a specific feed"""
        return self.feeds.get(feed_id)
    
    def list_feeds(self, category: Optional[FeedCategory] = None, enabled_only: bool = True) -> List[FeedSource]:
        """
        List all feeds, optionally filtered.
        
        Args:
            category: Filter by category
            enabled_only: Only return enabled feeds
        
        Returns:
            List of FeedSource objects
        """
        feeds = list(self.feeds.values())
        
        if category:
            feeds = [f for f in feeds if f.category == category]
        
        if enabled_only:
            feeds = [f for f in feeds if f.enabled]
        
        return feeds
    
    def get_feeds_by_publisher(self, publisher: str) -> List[FeedSource]:
        """Get all feeds from a specific publisher"""
        return [f for f in self.feeds.values() if f.publisher == publisher]


# CLI for managing feeds
if __name__ == "__main__":
    import sys
    from datetime import datetime
    
    registry = FeedRegistry()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "list":
            print("\n📰 Configured RSS Feeds:\n")
            for feed in registry.list_feeds(enabled_only=False):
                status = "✅" if feed.enabled else "⏸️ "
                print(f"{status} [{feed.category.value}] {feed.name}")
                print(f"   URL: {feed.url}")
                print(f"   Poll: Every {feed.poll_interval_minutes} minutes")
                print(f"   Articles: {feed.article_count}\n")
        
        elif command == "add" and len(sys.argv) >= 5:
            # Usage: python feed_sources.py add <feed_id> <name> <url> <category>
            feed_id = sys.argv[2]
            name = sys.argv[3]
            url = sys.argv[4]
            category = sys.argv[5] if len(sys.argv) > 5 else "real_estate"
            
            feed = FeedSource(
                feed_id=feed_id,
                name=name,
                url=url,
                category=FeedCategory(category),
                added_date=datetime.utcnow().isoformat()
            )
            registry.add_feed(feed)
        
        elif command == "remove" and len(sys.argv) >= 3:
            feed_id = sys.argv[2]
            registry.remove_feed(feed_id)
        
        elif command == "enable" and len(sys.argv) >= 3:
            feed_id = sys.argv[2]
            registry.update_feed(feed_id, enabled=True)
        
        elif command == "disable" and len(sys.argv) >= 3:
            feed_id = sys.argv[2]
            registry.update_feed(feed_id, enabled=False)
        
        else:
            print("""
Usage:
  python feed_sources.py list                                 - List all feeds
  python feed_sources.py add <id> <name> <url> <category>    - Add custom feed
  python feed_sources.py remove <id>                          - Remove feed
  python feed_sources.py enable <id>                          - Enable feed
  python feed_sources.py disable <id>                         - Disable feed
            """)
    else:
        # Default: show all feeds
        print("\n📰 Economic Times Realty Feeds Configured:\n")
        et_feeds = registry.get_feeds_by_publisher("Economic Times")
        for feed in et_feeds:
            print(f"✅ {feed.name}")
            print(f"   {feed.url}")
            print()
