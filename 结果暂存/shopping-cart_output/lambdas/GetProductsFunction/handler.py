import json
import os
import boto3
from decimal import Decimal
from datetime import datetime
from boto3.dynamodb.conditions import Key
import sys

# Add shared layer to path
sys.path.append('/opt/python')

from shared.logger import log_info, log_error, log_with_context, LoggingContext
from shared.error_handler import (
    handle_exception, 
    create_error_response, 
    wrap_lambda_handler,
    NotFoundError,
    ValidationError
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

def get_products_from_dynamodb():
    """Retrieve all products from DynamoDB"""
    if not table:
        return PRODUCT_LIST
    
    try:
        response = table.scan()
        products = []
        
        for item in response.get('Items', []):
            product = _dynamodb_to_python_obj(item)
            # Ensure product has required fields
            if 'product_id' in product:
                products.append(product)
        
        # If no products in DynamoDB, fall back to JSON file
        if not products and PRODUCT_LIST:
            return PRODUCT_LIST
            
        return products
    except Exception as e:
        log_error(f"Error retrieving products from DynamoDB: {str(e)}")
        # Fall back to JSON file
        return PRODUCT_LIST

@wrap_lambda_handler
def lambda_handler(event, context):
    """
    Lambda handler for GET /product
    Retrieve all products from the catalog
    """
    correlation_id = event.get('headers', {}).get('x-correlation-id') or event.get('requestContext', {}).get('requestId')
    request_id = context.aws_request_id if context else None
    
    with LoggingContext(correlation_id=correlation_id, request_id=request_id):
        log_info("GetProductsFunction invoked", 
                extra_fields={'http_method': event.get('httpMethod'), 
                             'path': event.get('path')})
        
        try:
            # Get products from DynamoDB
            products = get_products_from_dynamodb()
            
            log_info(f"Retrieved {len(products)} products")
            
            # Return success response
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
                },
                'body': json.dumps({'products': products})
            }
            
        except Exception as e:
            log_error(f"Error in GetProductsFunction: {str(e)}")
            # Return error response
            return create_error_response(
                status_code=500,
                error_code=ErrorCode.INTERNAL_ERROR,
                message="Failed to retrieve products",
                correlation_id=correlation_id,
                request_id=request_id
            )
