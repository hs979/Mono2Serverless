
"""
Logging utilities for serverless applications
Provides structured logging with correlation IDs and log levels
"""

import os
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
SERVICE_NAME = os.environ.get('SERVICE_NAME', 'shopping-cart-serverless')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# Configure the root logger
logger = logging.getLogger()
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Remove existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Add JSON formatter for structured logging
class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'service': SERVICE_NAME,
            'environment': ENVIRONMENT,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add correlation ID if available
        if hasattr(record, 'correlation_id'):
            log_data['correlation_id'] = record.correlation_id
        
        # Add request ID if available
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        # Add any extra fields
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

# Create console handler with JSON formatter
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance with the given name
    
    Args:
        name: Logger name (defaults to root logger)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

def log_with_context(
    level: str,
    message: str,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """
    Log a message with context information
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        correlation_id: Correlation ID for tracing requests across services
        request_id: Request ID for tracing individual requests
        extra_fields: Additional fields to include in the log
        **kwargs: Additional keyword arguments passed to the log method
    """
    log_func = getattr(logger, level.lower(), logger.info)
    
    # Create a log record with extra attributes
    extra = {}
    if correlation_id:
        extra['correlation_id'] = correlation_id
    if request_id:
        extra['request_id'] = request_id
    if extra_fields:
        extra['extra_fields'] = extra_fields
    
    log_func(message, extra=extra if extra else None, **kwargs)

def generate_correlation_id() -> str:
    """
    Generate a new correlation ID
    
    Returns:
        Correlation ID string
    """
    return str(uuid.uuid4())

# Convenience functions
def log_debug(message: str, **kwargs) -> None:
    """Log a debug message"""
    log_with_context('DEBUG', message, **kwargs)

def log_info(message: str, **kwargs) -> None:
    """Log an info message"""
    log_with_context('INFO', message, **kwargs)

def log_warning(message: str, **kwargs) -> None:
    """Log a warning message"""
    log_with_context('WARNING', message, **kwargs)

def log_error(message: str, **kwargs) -> None:
    """Log an error message"""
    log_with_context('ERROR', message, **kwargs)

def log_critical(message: str, **kwargs) -> None:
    """Log a critical message"""
    log_with_context('CRITICAL', message, **kwargs)

# Context manager for logging with correlation ID
class LoggingContext:
    """Context manager for logging with correlation ID"""
    
    def __init__(self, correlation_id: Optional[str] = None, request_id: Optional[str] = None):
        self.correlation_id = correlation_id or generate_correlation_id()
        self.request_id = request_id
        self.original_correlation_id = None
        self.original_request_id = None
    
    def __enter__(self):
        # Store original values
        self.original_correlation_id = getattr(logging, '_correlation_id', None)
        self.original_request_id = getattr(logging, '_request_id', None)
        
        # Set new values
        logging._correlation_id = self.correlation_id
        logging._request_id = self.request_id
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original values
        if self.original_correlation_id is not None:
            logging._correlation_id = self.original_correlation_id
        else:
            delattr(logging, '_correlation_id')
        
        if self.original_request_id is not None:
            logging._request_id = self.original_request_id
        else:
            delattr(logging, '_request_id')
        
        # Log any exception that occurred
        if exc_type is not None:
            log_error(f