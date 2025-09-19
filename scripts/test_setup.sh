#!/bin/bash

# Test Script for Remote Server Setup
# This script tests all the connections and endpoints

set -e

echo "Testing remote server setup..."

# Configuration
EXTERNAL_IP="193.246.150.25"
INTERNAL_IP="10.128.0.3"
FRONTEND_PORT="3000"
BACKEND_PORT="8000"

echo "Testing backend health endpoint..."
if curl -s http://$INTERNAL_IP:$BACKEND_PORT/health > /dev/null; then
    echo "✓ Backend health endpoint is working"
    curl -s http://$INTERNAL_IP:$BACKEND_PORT/health | python3 -m json.tool
else
    echo "✗ Backend health endpoint failed"
fi

echo ""
echo "Testing database info endpoint..."
if curl -s http://$INTERNAL_IP:$BACKEND_PORT/database/info > /dev/null; then
    echo "✓ Database info endpoint is working"
    curl -s http://$INTERNAL_IP:$BACKEND_PORT/database/info | python3 -m json.tool
else
    echo "✗ Database info endpoint failed"
fi

echo ""
echo "Testing frontend accessibility..."
if curl -s http://$EXTERNAL_IP:$FRONTEND_PORT > /dev/null; then
    echo "✓ Frontend is accessible at http://$EXTERNAL_IP:$FRONTEND_PORT"
else
    echo "✗ Frontend is not accessible"
fi

echo ""
echo "Testing PostgreSQL connection..."
if psql -h localhost -U analyzer_user -d query_analyzer -c "SELECT 'PostgreSQL connection successful!' as status;" > /dev/null 2>&1; then
    echo "✓ PostgreSQL connection is working"
else
    echo "✗ PostgreSQL connection failed"
fi

echo ""
echo "Testing complete!"
