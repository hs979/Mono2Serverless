"""
Error handling utilities for serverless applications
"""

import json
import traceback
from typing import Dict, Any, Optional
from enum import Enum

from .logger import log_error


class ErrorCode(Enum):
    """Standard error codes"""
    INTERNAL_ERROR = 1000
    VALIDATION_ERROR = 1001
    NOT_FOUND = 1002
    UNAUTHORIZED = 1003
    FORBIDDEN = 1004
    BAD_REQUEST = 1005
    CONFLICT = 1006
    PRODUCT_NOT_FOUND = 2000
    CART_NOT_FOUND = 3000


def handle_exception(exception: Exception, correlation_id: Optional[str] = None, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Handle exception and return error response"""
    log_error(f"Unhandled exception: {str(exception)}", 
              correlation_id=correlation_id,
              request_id=request_id,
              extra_fields={'stack_trace': traceback.format_exc()})
    
    return {
        'error_code': ErrorCode.INTERNAL_ERROR.value,
        'error_message': 'Internal server error',
        'error_type': exception.__class__.__name__,
        'correlation_id': correlation_id,
        'request_id': request_id
    }


def create_error_response(status_code: int, error_code: ErrorCode, message: str, 
                          correlation_id: Optional[str] = None, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Create API Gateway error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True
        },
        'body': json.dumps({
            'error_code': error_code.value,
            'error_message': message,
            'error_type': error_code.name,
            'correlation_id': correlation_id,
            'request_id': request_id
        })
    }


def wrap_lambda_handler(handler_func):
    """Decorator to wrap Lambda handlers with error handling"""
    def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        correlation_id = event.get('headers', {}).get('x-correlation-id') or event.get('requestContext', {}).get('requestId')
        request_id = context.aws_request_id if context else None
        
        try:
            return handler_func(event, context)
        except Exception as e:
            error_response = handle_exception(e, correlation_id, request_id)
            return create_error_response(500, ErrorCode.INTERNAL_ERROR, 'Internal server error', 
                                        correlation_id, request_id)
    return wrapper
