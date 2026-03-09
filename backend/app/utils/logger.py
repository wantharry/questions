"""
Centralized logging configuration using Loguru.
"""
import sys
from pathlib import Path
from loguru import logger
from app.config import settings


def setup_logging():
    """Configure application logging with file and console outputs."""
    
    # Remove default handler
    logger.remove()
    
    # Console handler with color
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )
    
    # File handler for all logs
    logger.add(
        settings.logs_dir / "app_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="00:00",  # Rotate at midnight
        retention="30 days",
        compression="zip",
    )
    
    # File handler for errors only
    logger.add(
        settings.logs_dir / "errors_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
        level="ERROR",
        rotation="00:00",
        retention="90 days",
        compression="zip",
    )
    
    # Ingestion-specific log
    logger.add(
        settings.logs_dir / "ingestion_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="INFO",
        rotation="00:00",
        retention="30 days",
        filter=lambda record: "ingestion" in record["extra"],
    )
    
    logger.info(f"Logging initialized. Log level: {settings.log_level}")
    return logger


# Initialize logger
app_logger = setup_logging()
