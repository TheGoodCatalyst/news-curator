"""
Structured JSON logging for observability across all microservices.
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Format logs as structured JSON"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": record.__dict__.get("service", "unknown"),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add custom fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data)


def get_logger(service_name: str, level: str = "INFO") -> logging.Logger:
    """
    Get a structured JSON logger for a service.
    
    Args:
        service_name: Name of the microservice (e.g., 'cognitive-processor')
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler with JSON formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Add service name to all log records
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.service = service_name
        return record
    
    logging.setLogRecordFactory(record_factory)
    
    return logger


def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs):
    """
    Log with additional context fields.
    
    Example:
        log_with_context(logger, "info", "Processing article", article_id="abc123", source="Reuters")
    """
    extra = {"extra_fields": kwargs}
    getattr(logger, level.lower())(message, extra=extra)
