#!/bin/bash

# Complete Remote Server Deployment Script
# This script handles the complete setup and deployment for the remote server

set -e

echo "🚀 Starting remote server deployment..."
echo "========================================"

# Configuration
EXTERNAL_IP="193.246.150.25"
INTERNAL_IP="10.128.0.3"
FRONTEND_PORT="3000"
BACKEND_PORT="8000"

echo "📋 Configuration:"
echo "  External IP: $EXTERNAL_IP"
echo "  Internal IP: $INTERNAL_IP"
echo "  Frontend Port: $FRONTEND_PORT"
echo "  Backend Port: $BACKEND_PORT"
echo ""

# Step 1: Stop any existing containers
echo "🛑 Stopping existing containers..."
podman-compose -f docker-compose.podman.yml down || true

# Step 2: Remove existing volumes for fresh start
echo "🗑️  Removing existing PostgreSQL volumes for fresh start..."
podman volume rm moretech_2025_postgres_data || true

# Step 3: Build and start services
echo "🔨 Building and starting services..."
podman-compose -f docker-compose.podman.yml up -d --build

# Step 4: Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 15

# Step 5: Setup PostgreSQL from scratch
echo "🗄️  Setting up PostgreSQL from scratch..."
./scripts/setup_postgres.sh

# Step 6: Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://$INTERNAL_IP:$BACKEND_PORT/health > /dev/null 2>&1; then
        echo "✅ Backend is ready!"
        break
    fi
    echo "   Backend is not ready yet, waiting... (attempt $((attempt + 1))/$max_attempts)"
    sleep 5
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Backend failed to start within the expected time"
    echo "📋 Checking backend logs:"
    podman-compose -f docker-compose.podman.yml logs backend
    exit 1
fi

# Step 7: Test connections
echo ""
echo "🧪 Testing connections..."
echo "=========================="

echo "🔍 Testing backend health endpoint..."
if curl -s http://$INTERNAL_IP:$BACKEND_PORT/health > /dev/null; then
    echo "✅ Backend health endpoint is working"
    curl -s http://$INTERNAL_IP:$BACKEND_PORT/health | python3 -m json.tool || echo "   (JSON parsing failed, but endpoint responded)"
else
    echo "❌ Backend health endpoint failed"
fi

echo ""
echo "🔍 Testing database info endpoint..."
if curl -s http://$INTERNAL_IP:$BACKEND_PORT/database/info > /dev/null; then
    echo "✅ Database info endpoint is working"
    curl -s http://$INTERNAL_IP:$BACKEND_PORT/database/info | python3 -m json.tool || echo "   (JSON parsing failed, but endpoint responded)"
else
    echo "❌ Database info endpoint failed"
fi

echo ""
echo "🔍 Testing PostgreSQL connection..."
if psql -h localhost -U analyzer_user -d query_analyzer -c "SELECT 'PostgreSQL connection successful!' as status;" > /dev/null 2>&1; then
    echo "✅ PostgreSQL connection is working"
else
    echo "❌ PostgreSQL connection failed"
fi

echo ""
echo "🔍 Testing frontend accessibility..."
if curl -s http://$EXTERNAL_IP:$FRONTEND_PORT > /dev/null; then
    echo "✅ Frontend is accessible at http://$EXTERNAL_IP:$FRONTEND_PORT"
else
    echo "⚠️  Frontend is not accessible yet, it may still be starting..."
    echo "   This is normal - React apps take time to build and start"
fi

echo ""
echo "🎉 Deployment completed!"
echo "======================="
echo ""
echo "📍 Access URLs:"
echo "  Frontend: http://$EXTERNAL_IP:$FRONTEND_PORT"
echo "  Backend:  http://$INTERNAL_IP:$BACKEND_PORT (internal only)"
echo ""
echo "🔧 Useful commands:"
echo "  View logs:     podman-compose -f docker-compose.podman.yml logs -f"
echo "  Stop services: podman-compose -f docker-compose.podman.yml down"
echo "  Restart:       podman-compose -f docker-compose.podman.yml restart"
echo ""
echo "📋 Service status:"
podman-compose -f docker-compose.podman.yml ps

echo ""
echo "✨ Setup complete! Your PostgreSQL Query Analyzer is now running on the remote server."
echo "   The frontend should be accessible at http://$EXTERNAL_IP:$FRONTEND_PORT"
echo "   If the frontend is not immediately accessible, wait a few minutes for React to build."
