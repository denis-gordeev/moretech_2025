#!/bin/bash

# Complete Deployment Script for Remote Server
# This script handles the complete setup and deployment

set -e

echo "Starting complete deployment..."

# Configuration
EXTERNAL_IP="193.246.150.25"
INTERNAL_IP="10.128.0.3"
FRONTEND_PORT="3000"
BACKEND_PORT="8000"

echo "Configuration:"
echo "  External IP: $EXTERNAL_IP"
echo "  Internal IP: $INTERNAL_IP"
echo "  Frontend Port: $FRONTEND_PORT"
echo "  Backend Port: $BACKEND_PORT"

# Stop any existing containers
echo "Stopping existing containers..."
docker-compose -f docker-compose.dev.yml down || true

# Remove existing volumes to start fresh
echo "Removing existing PostgreSQL volumes..."
docker volume rm moretech_2025_postgres_data || true

# Build and start services
echo "Building and starting services..."
docker-compose -f docker-compose.dev.yml up -d --build

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 10

# Run PostgreSQL setup
echo "Running PostgreSQL setup..."
./scripts/setup_postgres.sh

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
until curl -s http://$INTERNAL_IP:$BACKEND_PORT/health > /dev/null; do
    echo "Backend is not ready yet, waiting..."
    sleep 5
done

echo "Backend is ready!"

# Test connections
echo "Testing connections..."

echo "Testing backend health endpoint..."
curl -s http://$INTERNAL_IP:$BACKEND_PORT/health | python3 -m json.tool || echo "Backend health check failed"

echo "Testing database info endpoint..."
curl -s http://$INTERNAL_IP:$BACKEND_PORT/database/info | python3 -m json.tool || echo "Database info check failed"

# Check if frontend is accessible
echo "Checking frontend accessibility..."
if curl -s http://$EXTERNAL_IP:$FRONTEND_PORT > /dev/null; then
    echo "Frontend is accessible at http://$EXTERNAL_IP:$FRONTEND_PORT"
else
    echo "Frontend is not accessible yet, it may still be starting..."
fi

echo ""
echo "Deployment completed!"
echo ""
echo "Access URLs:"
echo "  Frontend: http://$EXTERNAL_IP:$FRONTEND_PORT"
echo "  Backend:  http://$INTERNAL_IP:$BACKEND_PORT (internal only)"
echo ""
echo "To check logs:"
echo "  docker-compose -f docker-compose.dev.yml logs -f"
echo ""
echo "To stop services:"
echo "  docker-compose -f docker-compose.dev.yml down"
