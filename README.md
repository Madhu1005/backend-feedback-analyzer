# Zoho Feedback Analyzer API

[![Tests](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/test.yml/badge.svg)](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/test.yml)
[![Code Quality](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/lint.yml/badge.svg)](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/lint.yml)
[![Docker Build](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/docker.yml/badge.svg)](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/docker.yml)
[![Security Scan](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/security.yml/badge.svg)](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/security.yml)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

LLM-powered feedback analysis API for real-time sentiment, emotion, and stress detection using Google Gemini 2.0 Flash.

## Features

- **🎯 Real-time Analysis**: Sentiment, emotion, stress level, and urgency detection
- **🛡️ Security First**: Input sanitization, PII detection/redaction, prompt injection defense
- **⚡ High Performance**: Rate limiting, Redis caching, async processing
- **🔍 Production Ready**: Comprehensive logging, health checks, error handling
- **📊 Rich Metadata**: Confidence scores, key phrases, action items, suggested replies
- **🐳 Docker Support**: Multi-stage builds, docker-compose for local development

## Quick Start

### Prerequisites

- Python 3.13+
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))
- Redis (optional, required for multi-worker deployments)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Madhu1005/backend-feedback-analyzer.git
cd backend-feedback-analyzer
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp example.env .env
# Edit .env and set your GEMINI_API_KEY
```

5. **Run the application**
```bash
uvicorn app.main:app --reload
```

Visit http://localhost:8000/docs for interactive API documentation.

## Docker Deployment

### Development with Docker Compose

```bash
# Copy and configure environment
cp example.env .env
# Edit .env with your GEMINI_API_KEY

# Start all services (API + Redis)
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

API available at: http://localhost:8000

### Production Deployment

```bash
# Build production image
docker build -t feedback-analyzer:latest .

# Run with production settings
docker run -d \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e DEBUG=false \
  -e GEMINI_API_KEY=your_key \
  -e RATE_LIMIT_STORAGE=redis://redis:6379/0 \
  -e CORS_ORIGINS=https://yourdomain.com \
  --name feedback-analyzer \
  feedback-analyzer:latest
```

For multi-worker production:
```bash
docker-compose --profile production up -d api-production
```

## API Usage

### Analyze a Message

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am extremely frustrated with the constant bugs in the latest release!",
    "user_id": "user123",
    "channel_id": "support"
  }'
```

**Response:**
```json
{
  "success": true,
  "analysis": {
    "sentiment": "negative",
    "emotion": "anger",
    "stress_score": 8,
    "category": "complaint",
    "key_phrases": ["extremely frustrated", "constant bugs"],
    "urgency": true,
    "confidence_scores": {
      "sentiment": 0.95,
      "emotion": 0.92,
      "category": 0.88,
      "stress": 0.90
    }
  },
  "sanitization": {
    "is_safe": true,
    "threat_level": "low",
    "modifications_made": false
  },
  "processing_time_ms": 1234.56,
  "llm_used": true
}
```

### Health Checks

```bash
# Liveness check
curl http://localhost:8000/health

# Readiness check (verifies LLM service)
curl http://localhost:8000/health/ready
```

## Configuration

All configuration via environment variables. See [`example.env`](example.env) for complete options.

### Key Settings

| Variable | Description | Default | Production |
|----------|-------------|---------|------------|
| `GEMINI_API_KEY` | Gemini API key | (required) | Required |
| `ENVIRONMENT` | Environment mode | `development` | `production` |
| `DEBUG` | Enable debug mode | `true` | `false` |
| `RATE_LIMIT_STORAGE` | Rate limiter storage | `memory://` | `redis://...` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` | Specific URLs |
| `LOG_LEVEL` | Logging level | `INFO` | `WARNING` |

### Production Checklist

✅ Set `ENVIRONMENT=production`  
✅ Set `DEBUG=false`  
✅ Configure Redis: `RATE_LIMIT_STORAGE=redis://redis:6379/0`  
✅ Restrict CORS: `CORS_ORIGINS=https://yourdomain.com`  
✅ Set `LOG_LEVEL=WARNING`  
✅ Review security settings  

## Development

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html

# Specific test file
pytest tests/test_api.py -v
```

**Test Coverage:** 237 tests covering all modules

### Project Structure

```
backend-feedback-analyzer/
├── app/
│   ├── api/              # API endpoints
│   │   ├── analyze.py    # Analysis endpoint
│   │   ├── health.py     # Health checks
│   │   └── routes.py     # Router aggregation
│   ├── core/             # Core functionality
│   │   ├── config.py     # Configuration
│   │   ├── llm_client.py # Gemini LLM client
│   │   ├── prompt_templates.py
│   │   └── sanitizer.py  # Input sanitization
│   ├── schemas/          # Pydantic models
│   │   └── analysis.py   # Request/response schemas
│   ├── services/         # Business logic
│   │   └── analyzer.py   # Analysis orchestration
│   └── main.py           # FastAPI application
├── tests/                # Test suite
├── Dockerfile            # Production container
├── docker-compose.yml    # Local development
├── requirements.txt      # Python dependencies
└── example.env           # Configuration template
```

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /api/v1/analyze
       ▼
┌─────────────────────────────────────────┐
│         FastAPI Application             │
│  ┌────────────────────────────────────┐ │
│  │  Rate Limiter (SlowAPI + Redis)    │ │
│  └────────────┬───────────────────────┘ │
│               ▼                          │
│  ┌────────────────────────────────────┐ │
│  │  Request Validation (Pydantic)     │ │
│  └────────────┬───────────────────────┘ │
│               ▼                          │
│  ┌────────────────────────────────────┐ │
│  │  Input Sanitizer                   │ │
│  │  - PII Detection/Redaction         │ │
│  │  - Prompt Injection Defense        │ │
│  │  - Threat Level Assessment         │ │
│  └────────────┬───────────────────────┘ │
│               ▼                          │
│  ┌────────────────────────────────────┐ │
│  │  Message Analyzer (Service)        │ │
│  └────────────┬───────────────────────┘ │
│               ▼                          │
│  ┌────────────────────────────────────┐ │
│  │  Gemini LLM Client                 │ │
│  │  - Retry with exponential backoff  │ │
│  │  - JSON repair & validation        │ │
│  │  - Fallback responses              │ │
│  └────────────┬───────────────────────┘ │
│               ▼                          │
│  ┌────────────────────────────────────┐ │
│  │  Response Enrichment               │ │
│  │  - Confidence scores               │ │
│  │  - Processing time                 │ │
│  │  - Sanitization metadata           │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## Security Features

- **Input Sanitization**: HTML escaping, control character removal, length limits
- **PII Protection**: Automatic detection and redaction of emails, phones, SSNs, credit cards
- **Prompt Injection Defense**: Pattern-based detection and neutralization
- **Rate Limiting**: Configurable per-minute limits with Redis backend
- **CORS**: Configurable origin restrictions
- **Non-root Container**: Docker runs as unprivileged user
- **Privacy-safe Logging**: Never logs user message content

## Performance

- **Latency**: ~1-2s average per analysis (includes LLM call)
- **Throughput**: 60 requests/minute (default, configurable)
- **Multi-worker**: Horizontal scaling with Redis rate limiter
- **Fallback**: Immediate response if LLM unavailable (<50ms)

## Monitoring

### Endpoints

- `GET /` - API information
- `GET /health` - Liveness check
- `GET /health/ready` - Readiness check with dependency validation
- `GET /docs` - OpenAPI documentation (dev only)

### Logs

Structured JSON logging with:
- Request ID tracking
- Processing time metrics
- Error tracing with stack traces
- Privacy-safe (no user content)

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Run tests: `pytest tests/`
4. Commit changes: `git commit -am 'Add feature'`
5. Push to branch: `git push origin feature/your-feature`
6. Submit a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions, please [open an issue](https://github.com/Madhu1005/backend-feedback-analyzer/issues).

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com)
- Powered by [Google Gemini](https://deepmind.google/technologies/gemini/)
- Rate limiting by [SlowAPI](https://github.com/laurentS/slowapi)