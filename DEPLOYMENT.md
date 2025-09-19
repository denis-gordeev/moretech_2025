# Remote Server Deployment Guide

This guide explains how to deploy the PostgreSQL Query Analyzer on a remote server with specific networking requirements.

## Server Configuration

- **External IP**: 193.246.150.25 (accessible from outside)
- **Internal IP**: 10.128.0.3 (only accessible from within the server)
- **Frontend Port**: 3000 (accessible externally)
- **Backend Port**: 8000 (only accessible internally)

## Quick Deployment

1. **Run the complete deployment script:**
   ```bash
   ./scripts/deploy.sh
   ```

2. **Test the setup:**
   ```bash
   ./scripts/test_setup.sh
   ```

## Manual Deployment Steps

If you prefer to run the steps manually:

### 1. Stop Existing Services
```bash
docker-compose -f docker-compose.dev.yml down
```

### 2. Clean PostgreSQL Data (Optional - for fresh start)
```bash
docker volume rm moretech_2025_postgres_data
```

### 3. Start Services
```bash
docker-compose -f docker-compose.dev.yml up -d --build
```

### 4. Setup PostgreSQL
```bash
./scripts/setup_postgres.sh
```

### 5. Test Connections
```bash
./scripts/test_setup.sh
```

## Configuration Changes Made

### Docker Compose (`docker-compose.dev.yml`)
- Backend bound to internal IP: `10.128.0.3:8000:8000`
- Frontend bound to external IP: `193.246.150.25:3000:3000`
- Frontend environment variable: `REACT_APP_API_URL=http://10.128.0.3:8000`

### Frontend (`frontend/src/services/api.js`)
- Default API URL changed to: `http://10.128.0.3:8000`

### Backend CORS (`backend/config.py`)
- Added external IP to CORS origins: `http://193.246.150.25:3000`

### Backend Security (`backend/security.py`)
- Added internal IP `10.128.0.3` to allowed hosts
- Modified blocked networks to exclude `10.128.0.3`

## Access URLs

- **Frontend**: http://193.246.150.25:3000/
- **Backend**: http://10.128.0.3:8000/ (internal only)

## Troubleshooting

### Check Service Status
```bash
docker-compose -f docker-compose.dev.yml ps
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.dev.yml logs -f

# Specific service
docker-compose -f docker-compose.dev.yml logs -f backend
docker-compose -f docker-compose.dev.yml logs -f frontend
docker-compose -f docker-compose.dev.yml logs -f postgres
```

### Test Backend Health
```bash
curl -s http://10.128.0.3:8000/health | python3 -m json.tool
```

### Test Database Connection
```bash
psql -h localhost -U analyzer_user -d query_analyzer -c "SELECT 'Connection successful!' as status;"
```

### Restart Services
```bash
docker-compose -f docker-compose.dev.yml restart
```

## Database Information

- **Database Name**: query_analyzer
- **Username**: analyzer_user
- **Password**: analyzer_pass
- **Connection String**: postgresql://analyzer_user:analyzer_pass@localhost:5432/query_analyzer

## Security Notes

- The backend is only accessible from the internal IP (10.128.0.3)
- CORS is configured to allow the external frontend IP
- PostgreSQL is only accessible from localhost within the container
- The internal IP (10.128.0.3) has been whitelisted in the security configuration
