# RSS Feed Ingestion - Quick Start Guide

## Overview

The News Curator platform now supports **custom RSS/XML feeds** with pre-configured **Economic Times Realty** feeds.

---

## Pre-Configured Feeds

The following Economic Times Realty feeds are already configured:

| Feed | Category | Poll Interval |
|------|----------|---------------|
| **Recent Stories** | Real Estate | 30 min |
| **Regulatory** | Regulatory | 60 min |
| **Industry** | Industry | 30 min |
| **Residential** | Residential | 45 min |
| **Housing Finance** | Housing Finance | 60 min |
| **Infrastructure** | Infrastructure | 60 min |

URLs:
```
https://realty.economictimes.indiatimes.com/rss/recentstories
https://realty.economictimes.indiatimes.com/rss/regulatory
https://realty.economictimes.indiatimes.com/rss/industry
https://realty.economictimes.indiatimes.com/rss/residential
https://realty.economictimes.indiatimes.com/rss/housing-finance
https://realty.economictimes.indiatimes.com/rss/infrastructure
```

---

## Quick Test

```bash
# Install dependencies
cd services/ingestion
pip install -r requirements.txt

# Test RSS poller
python rss_poller.py test

# Output:
# ✅ Fetched X articles from Economic Times Realty
# Shows titles, URLs, content previews
```

---

## Managing Feed Sources

### List All Feeds

```bash
python shared/config/feed_sources.py list
```

Output:
```
📰 Configured RSS Feeds:

✅ [real_estate] Economic Times Realty - Recent Stories
   URL: https://realty.economictimes.indiatimes.com/rss/recentstories
   Poll: Every 30 minutes

✅ [regulatory] Economic Times Realty - Regulatory
   ...
```

### Add Custom Feed

```bash
python shared/config/feed_sources.py add \
  my_custom_feed \
  "My Real Estate Blog" \
  "https://myblog.com/rss" \
  real_estate
```

### Enable/Disable Feeds

```bash
# Disable a feed
python shared/config/feed_sources.py disable et_realty_infrastructure

# Re-enable
python shared/config/feed_sources.py enable et_realty_infrastructure
```

### Remove Feed

```bash
python shared/config/feed_sources.py remove my_custom_feed
```

---

## Polling Feeds

### Poll All Feeds

```bash
# Poll all enabled feeds
python services/ingestion/rss_poller.py poll

# Poll only specific category
python services/ingestion/rss_poller.py poll real_estate
python services/ingestion/rss_poller.py poll regulatory
```

### Programmatic Usage

```python
from services.ingestion.rss_poller import RSSFeedPoller

poller = RSSFeedPoller()

# Poll all real estate feeds
articles = poller.poll_all_feeds(category="real_estate")

# Process articles
for article in articles:
    print(f"{article.title} - {article.source}")
    # Send to Kafka, process with AI, etc.

# Poll specific feed
articles = poller.poll_feed_by_id("et_realty_recent")
```

---

## Integration with Cognitive Processor

### Full Pipeline

```python
from services.ingestion.rss_poller import RSSFeedPoller
from services.cognitive.entity_extractor import EntityExtractor
from services.cognitive.causal_mapper import CausalMapper

# 1. Fetch articles
poller = RSSFeedPoller()
articles = poller.poll_all_feeds(category="real_estate")

# 2. Process with AI
extractor = EntityExtractor()
mapper = CausalMapper()

for article in articles:
    # Extract entities
    entities = extractor.extract(article.content)
    
    # Map causal relationships
    relationships = mapper.extract_relationships(article.content, entities)
    
    # Store in graph database
    # ...
```

---

## Feed Configuration File

Feeds are stored in `feed_sources.json`:

```json
{
  "feeds": [
    {
      "feed_id": "et_realty_recent",
      "name": "Economic Times Realty - Recent Stories",
      "url": "https://realty.economictimes.indiatimes.com/rss/recentstories",
      "category": "real_estate",
      "poll_interval_minutes": 30,
      "enabled": true,
      "publisher": "Economic Times",
      "language": "en",
      "country": "IN"
    }
  ]
}
```

---

## Scheduled Polling (Production)

### Option 1: Celery Beat

```python
# In celerybeat_schedule.py
from celery import Celery
from celery.schedules import crontab

app = Celery('news-curator')

@app.task
def poll_rss_feeds():
    poller = RSSFeedPoller()
    articles = poller.poll_all_feeds()
    # Publish to Kafka
    for article in articles:
        producer.send('raw-news', article.model_dump())

# Schedule
app.conf.beat_schedule = {
    'poll-rss-every-30min': {
        'task': 'poll_rss_feeds',
        'schedule': crontab(minute='*/30'),
    },
}
```

### Option 2: Cron Job

```bash
# Add to crontab
*/30 * * * * cd /path/to/news-curator && python services/ingestion/rss_poller.py poll
```

---

## Supported RSS/XML Features

✅ Standard RSS 2.0  
✅ Atom feeds  
✅ Custom namespaces  
✅ Media content (images, videos)  
✅ Author extraction  
✅ Category/tag extraction  
✅ Published date parsing  
✅ HTML content cleaning  

---

## Adding More News Sources

### Popular Indian News RSS Feeds

```python
from shared.config.feed_sources import FeedSource, FeedCategory, FeedRegistry
from datetime import datetime

registry = FeedRegistry()

# Times of India - Real Estate
registry.add_feed(FeedSource(
    feed_id="toi_realty",
    name="Times of India - Real Estate",
    url="https://timesofindia.indiatimes.com/rssfeeds/4719148.cms",
    category=FeedCategory.REAL_ESTATE,
    publisher="Times of India",
    added_date=datetime.utcnow().isoformat()
))

# Moneycontrol - Real Estate
registry.add_feed(FeedSource(
    feed_id="mc_realty",
    name="Moneycontrol - Real Estate",
    url="https://www.moneycontrol.com/rss/realestate.xml",
    category=FeedCategory.REAL_ESTATE,
    publisher="Moneycontrol",
    added_date=datetime.utcnow().isoformat()
))
```

---

## Troubleshooting

### Feed Not Parsing

```python
import feedparser

# Debug feed parsing
feed_url = "https://..."
parsed = feedparser.parse(feed_url)

print(f"Version: {parsed.version}")
print(f"Entries: {len(parsed.entries)}")

if parsed.bozo:
    print(f"Error: {parsed.bozo_exception}")
```

### No Articles Fetched

Check:
1. Feed is enabled: `python shared/config/feed_sources.py list`
2. Feed URL is accessible: `curl <feed_url>`
3. Articles might be duplicates (already seen)

---

## Next Steps

1. Set up automated polling (Celery or cron)
2. Integrate with Kafka pipeline
3. Process articles through Cognitive Processor
4. Store insights in Neo4j graph database

---

**Happy Feed Polling!** 📰
