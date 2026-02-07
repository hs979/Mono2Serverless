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
from layers.CommonUtilitiesLayer.python.db_utils import (
    get_table,
    dynamodb_to_python_obj
)

# Initialize DynamoDB resources
PRODUCTS_TABLE_NAME = os.environ.get('PRODUCTS_TABLE')
products_table = get_table(PRODUCTS_TABLE_NAME) if PRODUCTS_TABLE_NAME else None

def get_product_total_quantity(product_id):
    """Get total quantity of a product across all carts"""
    if not products_table:
        return 0
    
    try:
        response = products_table.get_item(
            Key={'product_id': product_id}
        )
        
        if 'Item' in response:
            total = response['Item'].get('total_quantity', 0)
            if isinstance(total, Decimal):
                return int(total) if total % 1 == 0 else float(total)
            return total
    except Exception as e:
        log_error(f"Error getting product total quantity: {str(e)}")
    
    return 0

@wrap_lambda_handler
def lambda_handler(event, context):
    """
    Lambda handler for GET /cart/{product_id}/total
    Calculate total quantity for a specific product in all carts
    """
    correlation_id = event.get('headers', {}).get('x-correlation-id') or event.get('requestContext', {}).get('requestId')
    request_id = context.aws_request_id if context else None
    
    with LoggingContext(correlation_id=correlation_id, request_id=request_id):
        # Extract product_id from path parameters
        product_id = event.get('pathParameters', {}).get('product_id')
        
        log_info(f"GetCartTotalFunction invoked for product_id: {product_id}", 
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
            # Get total quantity
            total = get_product_total_quantity(product_id)
            
            log_info(f"Total quantity for product {product_id}: {total}")
            
            # Return success response
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
                },
                'body': json.dumps({
                    'product': product_id,
                    'quantity': total
                })
            }
            
        except Exception as e:
            log_error(f"Error in GetCartTotalFunction: {str(e)}")
            return create_error_response(
                status_code=500,
                error_code=ErrorCode.INTERNAL_ERROR,
                message="Failed to get cart total",
                correlation_id=correlation_id,
                request_id=request_id
            )
