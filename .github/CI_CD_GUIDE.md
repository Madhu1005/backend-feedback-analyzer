# GitHub Actions CI/CD Pipeline

This document describes the automated CI/CD workflows for the Feedback Analyzer API.

## Workflows

### 1. Tests (`test.yml`)

**Trigger**: Push/PR to `main` or `develop`

**Jobs**:
- Runs on Python 3.11, 3.12, 3.13 (matrix strategy)
- Installs dependencies with pip caching
- Executes pytest with coverage reporting
- Uploads coverage to Codecov
- Tests health check endpoint with live server

**Required Secrets**:
- `GEMINI_API_KEY`: Google Gemini API key (optional for fallback tests)
- `CODECOV_TOKEN`: Codecov upload token (optional)

### 2. Code Quality (`lint.yml`)

**Trigger**: Push/PR to `main` or `develop`

**Jobs**:

**Lint Job**:
- Ruff linting with GitHub annotations
- Black code formatting check
- Mypy type checking

**Complexity Job**:
- Radon cyclomatic complexity analysis
- Maintainability index calculation

### 3. Docker Build (`docker.yml`)

**Trigger**: Push to `main`/`develop`, tags `v*.*.*`, PRs

**Jobs**:
- Builds multi-platform images (amd64, arm64)
- Pushes to GitHub Container Registry (ghcr.io)
- Generates semantic version tags
- Caches layers for faster builds
- Runs Trivy vulnerability scanning
- Tests image on PRs

**Image Tags**:
- `latest`: Latest main branch
- `main-<sha>`: Specific commit on main
- `v1.0.0`: Release versions
- `pr-123`: Pull request builds

**Required Permissions**:
- `contents: read`
- `packages: write`

### 4. Security Scan (`security.yml`)

**Trigger**: Push/PR to `main`, weekly schedule (Monday 00:00 UTC)

**Jobs**:

**Dependency Scan**:
- Safety check for known vulnerabilities
- pip-audit for security issues

**Container Scan**:
- Trivy image scanning
- Trivy filesystem scanning
- SARIF upload to GitHub Security

**Code Scan**:
- Bandit security linter
- Uploads detailed JSON report

**Secrets Scan**:
- TruffleHog for exposed secrets
- Scans commit history

## Setup Instructions

### 1. Enable GitHub Actions

Push workflows to `.github/workflows/` (already done).

### 2. Configure Secrets

Go to **Settings → Secrets and variables → Actions**:

**Required**:
- None (workflows run with defaults)

**Optional**:
- `GEMINI_API_KEY`: For testing LLM integration
- `CODECOV_TOKEN`: For coverage reporting to Codecov

### 3. Enable GitHub Container Registry

1. Go to **Settings → Actions → General**
2. Under "Workflow permissions", select:
   - ✅ Read and write permissions
   - ✅ Allow GitHub Actions to create and approve pull requests

3. Push to main to trigger first build:
```bash
git add .github/
git commit -m "Add CI/CD workflows"
git push origin main
```

### 4. View Container Images

Images published to: `ghcr.io/madhu1005/backend-feedback-analyzer`

Pull image:
```bash
docker pull ghcr.io/madhu1005/backend-feedback-analyzer:latest
```

### 5. Enable Security Scanning

1. Go to **Settings → Code security and analysis**
2. Enable:
   - ✅ Dependency graph
   - ✅ Dependabot alerts
   - ✅ Dependabot security updates
   - ✅ Code scanning (CodeQL)

## Workflow Status

Check status at: https://github.com/Madhu1005/backend-feedback-analyzer/actions

## Badge URLs

Add to README.md:
```markdown
[![Tests](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/test.yml/badge.svg)](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/test.yml)
[![Code Quality](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/lint.yml/badge.svg)](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/lint.yml)
[![Docker Build](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/docker.yml/badge.svg)](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/docker.yml)
[![Security Scan](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/security.yml/badge.svg)](https://github.com/Madhu1005/backend-feedback-analyzer/actions/workflows/security.yml)
```

## Deployment

### Manual Deployment

Pull and run the latest image:
```bash
docker pull ghcr.io/madhu1005/backend-feedback-analyzer:latest
docker run -d -p 8000:8000 \
  -e GEMINI_API_KEY=your_key \
  -e RATE_LIMIT_STORAGE=redis://redis:6379/0 \
  ghcr.io/madhu1005/backend-feedback-analyzer:latest
```

### Production Deployment

For production, create a separate workflow (`deploy.yml`):

```yaml
name: Deploy to Production

on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy feedback-analyzer \
            --image ghcr.io/madhu1005/backend-feedback-analyzer:${{ github.event.release.tag_name }} \
            --platform managed
```

## Troubleshooting

### Workflow Fails

1. Check workflow logs in Actions tab
2. Verify secrets are configured correctly
3. Ensure branch protection rules don't block CI

### Docker Build Fails

1. Check Dockerfile syntax
2. Verify all COPY paths exist
3. Check layer size limits

### Tests Fail

1. Run locally: `pytest -v`
2. Check if dependencies updated
3. Verify test environment variables

## Performance Optimization

### Caching

All workflows use caching:
- **pip cache**: Speeds up dependency installation
- **Docker layer cache**: Faster image builds
- **GitHub Actions cache**: Persistent across runs

### Matrix Strategy

Tests run in parallel across Python versions for faster feedback.

## Security Best Practices

✅ Workflows run in isolated environments  
✅ Secrets never logged or exposed  
✅ SARIF reports uploaded to Security tab  
✅ Container images scanned before publish  
✅ Dependencies audited on every push  
✅ Code scanned for security vulnerabilities  
✅ Weekly scheduled scans for zero-days  

## Next Steps

1. **Push workflows**: Commit and push to trigger first run
2. **Monitor**: Watch Actions tab for results
3. **Configure secrets**: Add GEMINI_API_KEY if needed
4. **Enable Dependabot**: Auto-update dependencies
5. **Add deployment**: Create deploy workflow for your cloud provider
