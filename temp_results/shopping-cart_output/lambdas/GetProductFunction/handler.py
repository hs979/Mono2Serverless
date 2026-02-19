import json
import os
import boto3
from decimal import Decimal
import sys

# Add shared layer to path
sys.path.append('/opt/python')

from shared.logger import log_info, log_error, log_with_context, LoggingContext
from shared.error_handler import (
    handle_exception, 
    create_error_response, 
    wrap_lambda_handler,
    ErrorCode
)

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
PRODUCTS_TABLE_NAME = os.environ.get('PRODUCTS_TABLE')
table = dynamodb.Table(PRODUCTS_TABLE_NAME) if PRODUCTS_TABLE_NAME else None

# Load product data from JSON file (for backward compatibility)
import os as _os
_current_dir = _os.path.dirname(_os.path.abspath(__file__))
_product_file = _os.path.join(_current_dir, '..', '..', '..', 'shopping-cart', 'product_list.json')
try:
    with open(_product_file, 'r', encoding='utf-8') as f:
        PRODUCT_LIST = json.load(f)
except:
    PRODUCT_LIST = []

def _dynamodb_to_python_obj(obj):
    """Convert DynamoDB object to Python standard object"""
    if isinstance(obj, dict):
        return {k: _dynamodb_to_python_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_dynamodb_to_python_obj(item) for item in obj]
    elif isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj

def get_product_from_dynamodb(product_id):
    """Retrieve a specific product from DynamoDB"""
    if not table:
        # Fall back to JSON file
        return next((p for p in PRODUCT_LIST if p['productId'] == product_id), None)
    
    try:
        response = table.get_item(
            Key={'product_id': product_id}
        )
        
        if 'Item' in response:
            return _dynamodb_to_python_obj(response['Item'])
        else:
            return None
    except Exception as e:
        log_error(f"Error retrieving product from DynamoDB: {str(e)}")
        # Fall back to JSON file
        return next((p for p in PRODUCT_LIST if p['productId'] == product_id), None)

@wrap_lambda_handler
def lambda_handler(event, context):
    """
    Lambda handler for GET /product/{product_id}
    Retrieve a specific product by ID
    """
    correlation_id = event.get('headers', {}).get('x-correlation-id') or event.get('requestContext', {}).get('requestId')
    request_id = context.aws_request_id if context else None
    
    with LoggingContext(correlation_id=correlation_id, request_id=request_id):
        # Extract product_id from path parameters
        product_id = event.get('pathParameters', {}).get('product_id')
        
        log_info(f"GetProductFunction invoked for product_id: {product_id}", 
                extra_fields={'http_method': event.get('httpMethod'), 
                             'path': event.get('path'),
                             'product_id': product_id})
        
        if not product_id:
            return create_error_response(
                status_code=400,
                error_code=ErrorCode.VALIDATION_ERROR,
                message="Product ID is required",
                correlation_id=correlation_id,
                request_id=request_id
            )
        
        try:
            # Get product from DynamoDB
            product = get_product_from_dynamodb(product_id)
            
            if not product:
                return create_error_response(
                    status_code=404,
                    error_code=ErrorCode.PRODUCT_NOT_FOUND,
                    message=f"Product with ID '{product_id}' not found",
                    correlation_id=correlation_id,
                    request_id=request_id
                )
            
            log_info(f"Retrieved product: {product_id}")
            
            # Return success response
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
                },
                'body': json.dumps({'product': product})
            }
            
        except Exception as e:
            log_error(f"Error in GetProductFunction: {str(e)}")
            return create_error_response(
                status_code=500,
                error_code=ErrorCode.INTERNAL_ERROR,
                message="Failed to retrieve product",
                correlation_id=correlation_id,
                request_id=request_id
            )
