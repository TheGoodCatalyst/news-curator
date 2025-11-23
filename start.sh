#!/bin/bash
# Quick start script for News Curator platform

echo "🚀 News Curator - Quick Start Script"
echo "===================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
    echo "   - OPENAI_API_KEY (required)"
    echo "   - CRUNCHBASE_API_KEY (optional, for fact-checking)"
    echo "   - PINECONE_API_KEY (optional, for Phase 2)"
    echo ""
    echo "Please update .env and run this script again."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Start infrastructure
echo "🔧 Starting infrastructure services..."
docker-compose up -d zookeeper kafka neo4j postgres redis

echo ""
echo "⏳ Waiting for services to be healthy (30 seconds)..."
sleep 30

# Check service health
echo ""
echo "🔍 Checking service health..."
docker-compose ps

echo ""
echo "📊 Service URLs:"
echo "   - Neo4j Browser: http://localhost:7474"
echo "   - Kafka: localhost:9093 (external)"
echo "   - PostgreSQL: localhost:5432"
echo "   - Redis: localhost:6379"
echo ""

# Start Cognitive Processor
echo "🧠 Starting Cognitive Processor..."
docker-compose up -d cognitive-processor

echo ""
echo "✅ All services started!"
echo ""
echo "📋 Next steps:"
echo "   1. Check logs: docker logs -f cognitive-processor"
echo "   2. View Neo4j: open http://localhost:7474 (user: neo4j, password: check .env)"
echo "   3. Test the system: python scripts/test_producer.py (coming in Phase 2)"
echo ""
echo "🛑 To stop: docker-compose down"
echo "🗑️  To reset: docker-compose down -v (⚠️ deletes all data)"
