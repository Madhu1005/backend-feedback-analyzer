"""
Package initialization for API module.

Exports:
- analyze: Analysis endpoints
- health: Health check endpoints
- routes: Aggregated router with versioning
"""
from app.api import analyze, health, routes

__all__ = ["analyze", "health", "routes"]
