#!/bin/bash

echo "🚀 Starting Grafana KPI Extractor Environment..."
echo "=================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker with Compose plugin first."
    exit 1
fi

# Start services
echo "📦 Starting services..."
docker compose up -d --remove-orphans

# Wait for services to be ready
echo "⏳ Waiting for services to initialize..."
sleep 10

# Check if services are running
echo "🔍 Checking service status..."
docker compose ps

# Wait for Grafana to be fully ready
echo "⏳ Waiting for Grafana to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        echo "✅ Grafana is ready!"
        break
    fi
    echo "   Attempt $i/30: Waiting for Grafana..."
    sleep 2
done

# Check if data generation completed
echo "📊 Checking data generation status..."
docker compose logs data-generator | tail -5

echo ""
echo "🎉 Environment is ready!"
echo "=================================================="
echo "📊 Grafana Dashboard: http://localhost:3000"
echo "👤 Username: admin"
echo "🔑 Password: admin"
echo ""
echo "📋 Available Dashboards:"
echo "   • Views and Edits: http://localhost:3000/d/views-edits-dashboard"
echo "   • Alarms: http://localhost:3000/d/alarms-dashboard"
echo ""
echo "📖 Task Instructions: See TASK.md"
echo "🛠️  Setup Guide: See README.md"
echo ""
echo "To stop the environment: docker compose down"
echo "To reset everything: docker compose down -v" 