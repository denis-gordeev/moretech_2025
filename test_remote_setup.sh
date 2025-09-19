#!/bin/bash

# Test Script for Remote Server Setup
# This script tests all the connections and endpoints

set -e

echo "🧪 Testing remote server setup..."
echo "================================="

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

# Test backend health endpoint
echo "🔍 Testing backend health endpoint..."
if curl -s http://$INTERNAL_IP:$BACKEND_PORT/health > /dev/null; then
    echo "✅ Backend health endpoint is working"
    echo "   Response:"
    curl -s http://$INTERNAL_IP:$BACKEND_PORT/health | python3 -m json.tool 2>/dev/null || echo "   (Raw response received)"
else
    echo "❌ Backend health endpoint failed"
fi

echo ""

# Test database info endpoint
echo "🔍 Testing database info endpoint..."
if curl -s http://$INTERNAL_IP:$BACKEND_PORT/database/info > /dev/null; then
    echo "✅ Database info endpoint is working"
    echo "   Response:"
    curl -s http://$INTERNAL_IP:$BACKEND_PORT/database/info | python3 -m json.tool 2>/dev/null || echo "   (Raw response received)"
else
    echo "❌ Database info endpoint failed"
fi

echo ""

# Test frontend accessibility
echo "🔍 Testing frontend accessibility..."
if curl -s http://$EXTERNAL_IP:$FRONTEND_PORT > /dev/null; then
    echo "✅ Frontend is accessible at http://$EXTERNAL_IP:$FRONTEND_PORT"
else
    echo "❌ Frontend is not accessible"
    echo "   This might be normal if the React app is still building"
fi

echo ""

# Test PostgreSQL connection
echo "🔍 Testing PostgreSQL connection..."
if psql -h localhost -U analyzer_user -d query_analyzer -c "SELECT 'PostgreSQL connection successful!' as status;" > /dev/null 2>&1; then
    echo "✅ PostgreSQL connection is working"
else
    echo "❌ PostgreSQL connection failed"
fi

echo ""

# Test CORS headers
echo "🔍 Testing CORS headers..."
response=$(curl -s -I -X OPTIONS -H "Origin: http://$EXTERNAL_IP:$FRONTEND_PORT" http://$INTERNAL_IP:$BACKEND_PORT/health)
if echo "$response" | grep -q "Access-Control-Allow-Origin"; then
    echo "✅ CORS headers are present"
    echo "   CORS headers found:"
    echo "$response" | grep -i "access-control" || echo "   (No CORS headers visible in response)"
else
    echo "❌ CORS headers not found"
fi

echo ""

# Test private network header
echo "🔍 Testing Access-Control-Allow-Private-Network header..."
if echo "$response" | grep -qi "Access-Control-Allow-Private-Network"; then
    echo "✅ Access-Control-Allow-Private-Network header is present"
else
    echo "❌ Access-Control-Allow-Private-Network header not found"
fi

echo ""

# Show service status
echo "📋 Podman service status:"
podman-compose -f docker-compose.podman.yml ps

echo ""
echo "🎯 Testing complete!"
echo "==================="
echo ""
echo "📍 If all tests pass, your application should be accessible at:"
echo "   Frontend: http://$EXTERNAL_IP:$FRONTEND_PORT"
echo ""
echo "🔧 If there are issues, check the logs with:"
echo "   podman-compose -f docker-compose.podman.yml logs -f"
