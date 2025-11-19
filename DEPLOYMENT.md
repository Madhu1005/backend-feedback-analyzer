# Deployment Guide

## Quick Deployment Options

### 1. Local Development (Recommended)

```bash
# Setup
cp example.env .env
# Edit .env and add your GEMINI_API_KEY

# Start services
docker-compose up -d

# View logs
docker-compose logs -f api

# Test API
curl http://localhost:8000/health

# Stop services
docker-compose down
```

**Includes:**
- FastAPI application on port 8000
- Redis for rate limiting
- Hot-reload for development
- Interactive API docs at http://localhost:8000/docs

### 2. Production Deployment

```bash
# Build image
docker build -t feedback-analyzer:latest .

# Run with environment file
docker run -d \
  --name feedback-analyzer \
  -p 8000:8000 \
  --env-file .env.production \
  feedback-analyzer:latest

# Check health
curl http://localhost:8000/health/ready
```

### 3. Multi-Worker Production

```bash
# Use production profile in docker-compose
docker-compose --profile production up -d

# Verify
curl http://localhost:8001/health
```

**Features:**
- 4 Uvicorn workers
- Redis rate limiting
- Production logging
- Strict CORS

## Environment Configuration

### Required Variables

```env
GEMINI_API_KEY=your_api_key_here
```

### Production Settings

```env
ENVIRONMENT=production
DEBUG=false
RATE_LIMIT_STORAGE=redis://redis:6379/0
CORS_ORIGINS=https://yourdomain.com
LOG_LEVEL=WARNING
```

## Cloud Deployment

### AWS ECS

1. Push image to ECR:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker tag feedback-analyzer:latest <account>.dkr.ecr.us-east-1.amazonaws.com/feedback-analyzer:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/feedback-analyzer:latest
```

2. Create ECS task definition with:
   - Container port: 8000
   - Environment variables from Secrets Manager
   - Health check: `/health`
   - Redis from ElastiCache

### Google Cloud Run

```bash
gcloud run deploy feedback-analyzer \
  --image gcr.io/your-project/feedback-analyzer \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key \
  --set-env-vars ENVIRONMENT=production
```

### Azure Container Instances

```bash
az container create \
  --resource-group feedback-analyzer \
  --name feedback-analyzer-api \
  --image feedback-analyzer:latest \
  --dns-name-label feedback-analyzer \
  --ports 8000 \
  --environment-variables \
    GEMINI_API_KEY=your_key \
    ENVIRONMENT=production
```

## Monitoring

### Health Checks

- **Liveness**: `GET /health` - Always returns 200 if app running
- **Readiness**: `GET /health/ready` - Returns 503 if LLM unavailable

### Logs

View logs:
```bash
docker logs -f feedback-analyzer

# With docker-compose
docker-compose logs -f api
```

### Metrics

Custom headers in responses:
- `X-Request-ID`: Unique request identifier
- `X-Process-Time`: Processing time in milliseconds

## Scaling

### Horizontal Scaling

Requirements for multiple instances:
1. Redis for rate limiting: `RATE_LIMIT_STORAGE=redis://...`
2. Load balancer in front
3. Shared Redis instance

### Vertical Scaling

Increase container resources:
```bash
docker run -d \
  --cpus="2.0" \
  --memory="4g" \
  feedback-analyzer:latest
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs feedback-analyzer

# Common issues:
# - Missing GEMINI_API_KEY
# - Invalid Redis connection
# - Port 8000 already in use
```

### Health check failing

```bash
# Test from inside container
docker exec feedback-analyzer curl http://localhost:8000/health

# Check if API key is valid
docker exec feedback-analyzer env | grep GEMINI_API_KEY
```

### Rate limiting not working

- Verify Redis connection: `RATE_LIMIT_STORAGE=redis://redis:6379/0`
- Check Redis is running: `docker ps | grep redis`
- Test Redis: `docker exec redis redis-cli ping`

## Security Checklist

✅ Use secrets management (not plain .env in production)  
✅ Enable HTTPS/TLS  
✅ Restrict CORS origins  
✅ Use non-root container user (already configured)  
✅ Scan images for vulnerabilities  
✅ Set resource limits  
✅ Use private container registry  
✅ Rotate API keys regularly  

## Performance Tuning

### Workers

For CPU-bound workloads:
```bash
# Workers = (2 x CPU cores) + 1
uvicorn app.main:app --workers 9 --host 0.0.0.0
```

### Rate Limits

Adjust per environment:
```env
# Development: lenient
RATE_LIMIT_PER_MINUTE=120

# Production: strict
RATE_LIMIT_PER_MINUTE=60
```

### Timeouts

```env
LLM_TIMEOUT=30  # Gemini API timeout
RESPONSE_TIMEOUT=60  # HTTP response timeout
```

## Backup & Recovery

### Redis Data

```bash
# Backup
docker exec redis redis-cli SAVE
docker cp redis:/data/dump.rdb ./backup/

# Restore
docker cp ./backup/dump.rdb redis:/data/
docker restart redis
```

## Updates

### Rolling Update

```bash
# Build new version
docker build -t feedback-analyzer:v2 .

# Start new container
docker run -d --name feedback-analyzer-v2 -p 8001:8000 feedback-analyzer:v2

# Test new version
curl http://localhost:8001/health

# Switch traffic (update load balancer)
# Stop old version
docker stop feedback-analyzer
docker rm feedback-analyzer
```

## Support

For issues:
- Check logs: `docker logs feedback-analyzer`
- Review configuration: `docker exec feedback-analyzer env`
- Test health: `curl http://localhost:8000/health/ready`
- Open issue: https://github.com/Madhu1005/backend-feedback-analyzer/issues
