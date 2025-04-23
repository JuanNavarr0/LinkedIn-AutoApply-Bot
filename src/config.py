"""
Configuration module for the LinkedIn job application bot.

This module loads environment variables and provides access to configuration
settings used throughout the application.
"""

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

class Config:
    """
    Application configuration class.

    Reads configuration values from environment variables.
    """
    LINKEDIN_EMAIL: Optional[str] = os.getenv("LINKEDIN_EMAIL")
    LINKEDIN_PASSWORD: Optional[str] = os.getenv("LINKEDIN_PASSWORD")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL", "sqlite:///jobs.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> None:
        """Validate that essential configuration variables are set."""
        required_vars = ["LINKEDIN_EMAIL", "LINKEDIN_PASSWORD"]
        missing_vars = [var for var in required_vars if getattr(cls, var) is None]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Instantiate the config object for easy import
config = Config()

# Validate configuration on import
try:
    config.validate()
except ValueError as e:
    print(f"Configuration Error: {e}")
    # Uncomment to exit on config error if needed
    # exit(1)