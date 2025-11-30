"""
Test configuration for load testing.

Usage:
    export FLASK_CONFIG=test_config
    python barquina.py
"""

from app.config import Config


class TestConfig(Config):
    """Configuration for load testing."""
    
    TESTING = False  # Not unit testing, but load testing
    LOGIN_DISABLED = True  # Disable authentication for load tests
    
    # Optimize for testing
    SQLALCHEMY_ECHO = False
    
    # Optional: Use in-memory database for faster tests
    # SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    
    # Keep development database but disable debug
    DEBUG = False
