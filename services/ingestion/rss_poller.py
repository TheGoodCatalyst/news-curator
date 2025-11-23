"""
RSS Feed Poller and Parser

Fetches and parses RSS/XML feeds, converts to standardized article events.
Supports custom feed sources including Economic Times Realty feeds.
"""
import feedparser
import hashlib
from typing import List, Optional, Dict
from datetime import datetime
import time
from urllib.parse import urlparse

from shared.models import RawArticleEvent
from shared.config.feed_sources import FeedRegistry, FeedSource
from shared.utils import get_logger, log_with_context

logger = get_logger("rss-poller")


class RSSFeedPoller:
    """
    Polls RSS/XML feeds and converts entries to RawArticleEvent objects.
    
    Features:
    - Automatic feed parsing
    - Deduplication based on URL/GUID
    - Content extraction and cleaning
    - Error handling and retry logic
    """
    
    def __init__(self, feed_registry: Optional[FeedRegistry] = None):
        """Initialize poller with feed registry"""
        self.feed_registry = feed_registry or FeedRegistry()
        self.seen_articles: set = set()  # Simple in-memory dedup (use Redis in production)
    
    def poll_feed(self, feed: FeedSource) -> List[RawArticleEvent]:
        """
        Poll a single RSS feed and return articles.
        
        Args:
            feed: FeedSource configuration
        
        Returns:
            List of RawArticleEvent objects
        """
        try:
            log_with_context(
                logger, "info",
                f"Polling feed: {feed.name}",
                feed_id=feed.feed_id,
                url=str(feed.url)
            )
            
            # Parse RSS feed
            parsed_feed = feedparser.parse(str(feed.url))
            
            # Check for errors
            if parsed_feed.bozo:
                logger.warning(f"Feed parsing error: {parsed_feed.bozo_exception}")
            
            articles = []
            
            # Process each entry
            for entry in parsed_feed.entries:
                try:
                    article = self._parse_entry(entry, feed)
                    
                    # Deduplicate
                    if article and article.article_id not in self.seen_articles:
                        articles.append(article)
                        self.seen_articles.add(article.article_id)
                
                except Exception as e:
                    logger.warning(f"Failed to parse feed entry: {e}")
                    continue
            
            log_with_context(
                logger, "info",
                f"Fetched {len(articles)} new articles from {feed.name}",
                feed_id=feed.feed_id,
                article_count=len(articles)
            )
            
            # Update feed metadata
            self.feed_registry.update_feed(
                feed.feed_id,
                last_fetched=datetime.utcnow().isoformat(),
                article_count=feed.article_count + len(articles)
            )
            
            return articles
        
        except Exception as e:
            logger.error(f"Failed to poll feed {feed.name}: {e}")
            return []
    
    def _parse_entry(self, entry: Dict, feed: FeedSource) -> Optional[RawArticleEvent]:
        """
        Parse a single feed entry into RawArticleEvent.
        
        Args:
            entry: Feed entry dict from feedparser
            feed: Source feed configuration
        
        Returns:
            RawArticleEvent or None
        """
        try:
            # Extract URL (primary or alternate)
            url = entry.get('link') or entry.get('id')
            if not url:
                return None
            
            # Generate article ID from URL
            article_id = hashlib.md5(url.encode()).hexdigest()[:16]
            
            # Extract title
            title = entry.get('title', 'Untitled')
            
            # Extract content (try multiple fields)
            content = ""
            if 'content' in entry and entry.content:
                content = entry.content[0].get('value', '')
            elif 'summary' in entry:
                content = entry.summary
            elif 'description' in entry:
                content = entry.description
            
            # Clean HTML tags from content
            content = self._clean_html(content)
            
            # Extract author
            author = None
            if 'author' in entry:
                author = entry.author
            elif 'authors' in entry and entry.authors:
                author = entry.authors[0].get('name')
            
            # Extract published date
            published_date = None
            if 'published_parsed' in entry and entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])
            elif 'updated_parsed' in entry and entry.updated_parsed:
                published_date = datetime(*entry.updated_parsed[:6])
            else:
                published_date = datetime.utcnow()
            
            # Extract tags/categories
            tags = []
            if 'tags' in entry:
                tags = [tag.get('term', '') for tag in entry.tags]
            
            # Create RawArticleEvent
            article = RawArticleEvent(
                article_id=f"rss_{article_id}",
                url=url,
                title=title,
                content=content or title,  # Fallback to title if no content
                source=feed.publisher or self._extract_domain(url),
                published_date=published_date,
                fetch_timestamp=datetime.utcnow(),
                author=author,
                tags=tags
            )
            
            return article
        
        except Exception as e:
            logger.warning(f"Failed to parse entry: {e}")
            return None
    
    def _clean_html(self, html_content: str) -> str:
        """Remove HTML tags from content"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
        except ImportError:
            # Fallback: simple regex-based cleaning
            import re
            clean = re.sub(r'<[^>]+>', '', html_content)
            return clean.strip()
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            # Remove 'www.' prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return "Unknown"
    
    def poll_all_feeds(self, category: Optional[str] = None) -> List[RawArticleEvent]:
        """
        Poll all enabled feeds.
        
        Args:
            category: Optional category filter
        
        Returns:
            List of all articles from all feeds
        """
        from shared.config.feed_sources import FeedCategory
        
        # Get feeds to poll
        cat_filter = FeedCategory(category) if category else None
        feeds_to_poll = self.feed_registry.list_feeds(
            category=cat_filter,
            enabled_only=True
        )
        
        log_with_context(
            logger, "info",
            f"Polling {len(feeds_to_poll)} feeds",
            feed_count=len(feeds_to_poll),
            category=category
        )
        
        all_articles = []
        
        for feed in feeds_to_poll:
            articles = self.poll_feed(feed)
            all_articles.extend(articles)
            
            # Be nice to servers - rate limiting
            time.sleep(2)
        
        log_with_context(
            logger, "info",
            f"Total articles fetched: {len(all_articles)}",
            total_articles=len(all_articles)
        )
        
        return all_articles
    
    def poll_feed_by_id(self, feed_id: str) -> List[RawArticleEvent]:
        """Poll a specific feed by ID"""
        feed = self.feed_registry.get_feed(feed_id)
        if not feed:
            logger.error(f"Feed not found: {feed_id}")
            return []
        
        if not feed.enabled:
            logger.warning(f"Feed is disabled: {feed_id}")
            return []
        
        return self.poll_feed(feed)


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    poller = RSSFeedPoller()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "test":
            # Test with Economic Times Realty Recent Stories
            print("\n🧪 Testing RSS Feed Polling\n")
            print("Fetching: Economic Times Realty - Recent Stories")
            
            articles = poller.poll_feed_by_id("et_realty_recent")
            
            print(f"\n✅ Fetched {len(articles)} articles\n")
            
            # Show first 3 articles
            for i, article in enumerate(articles[:3], 1):
                print(f"--- Article {i} ---")
                print(f"Title: {article.title}")
                print(f"Source: {article.source}")
                print(f"Published: {article.published_date}")
                print(f"URL: {article.url}")
                print(f"Content preview: {article.content[:200]}...")
                print(f"Tags: {', '.join(article.tags)}\n")
        
        elif command == "poll":
            # Poll all feeds
            category = sys.argv[2] if len(sys.argv) > 2 else None
            print(f"\n📡 Polling all feeds" + (f" (category: {category})" if category else ""))
            
            articles = poller.poll_all_feeds(category=category)
            
            print(f"\n✅ Total articles: {len(articles)}")
            
            # Group by source
            by_source = {}
            for article in articles:
                by_source[article.source] = by_source.get(article.source, 0) + 1
            
            print("\nBreakdown by source:")
            for source, count in by_source.items():
                print(f"  {source}: {count} articles")
        
        else:
            print("""
Usage:
  python rss_poller.py test                    - Test with Economic Times Realty feed
  python rss_poller.py poll [category]         - Poll all enabled feeds
            """)
    else:
        # Default: test mode
        print("\n📰 RSS Feed Poller - Test Mode\n")
        articles = poller.poll_feed_by_id("et_realty_recent")
        print(f"✅ Fetched {len(articles)} articles from Economic Times Realty")
