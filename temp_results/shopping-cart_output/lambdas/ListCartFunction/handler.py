import json
import os
import boto3
from decimal import Decimal
from datetime import datetime
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
    dynamodb_to_python_obj,
    python_obj_to_dynamodb
)

# Initialize DynamoDB resources
CARTS_TABLE_NAME = os.environ.get('CARTS_TABLE')
PRODUCTS_TABLE_NAME = os.environ.get('PRODUCTS_TABLE')

carts_table = get_table(CARTS_TABLE_NAME) if CARTS_TABLE_NAME else None
products_table = get_table(PRODUCTS_TABLE_NAME) if PRODUCTS_TABLE_NAME else None

def get_user_identifier(event):
    """
    Get user identifier from the request
    Returns: (pk, is_authenticated)
    """
    # Check for Authorization header (Cognito)
    auth_header = event.get('headers', {}).get('Authorization') or event.get('headers', {}).get('authorization')
    
    if auth_header:
        try:
            # Extract user ID from Cognito token
            # In production, this would verify the JWT token
            import re
            # Simple extraction for demo - in real app, verify JWT
            token = auth_header.replace('Bearer ', '')
            # For demo, assume token contains user_id
            # In real app, decode and verify JWT
            user_id = 'demo-user-id'  # This would come from JWT verification
            return f"user#{user_id}", True
        except:
            pass
    
    # Check for cart ID in headers or generate new
    cart_id = event.get('headers', {}).get('x-cart-id')
    if not cart_id:
        import uuid
        cart_id = str(uuid.uuid4())
    
    return f"cart#{cart_id}", False

def get_cart_items(pk):
    """Get all items in a cart"""
    if not carts_table:
        return []
    
    try:
        from boto3.dynamodb.conditions import Key
        
        # Query cart items (sk begins with 'product#')
        response = carts_table.query(
            KeyConditionExpression=Key('cart_id').eq(pk) & Key('product_id').begins_with('product#')
        )
        
        items = []
        current_time = datetime.now()
        
        for item in response.get('Items', []):
            # Filter out expired items
            expires_at = item.get('expires_at')
            if expires_at:
                try:
                    exp_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if exp_datetime < current_time:
                        continue
                except:
                    pass
            
            # Filter out zero quantity items
            quantity = item.get('quantity', 0)
            if isinstance(quantity, Decimal):
                quantity = int(quantity) if quantity % 1 == 0 else float(quantity)
            
            if quantity <= 0:
                continue
            
            # Get product details
            product_id = item.get('product_id', '').replace('product#', '')
            product_detail = item.get('product_detail', {})
            
            items.append({
                'productId': product_id,
                'quantity': quantity,
                'productDetail': dynamodb_to_python_obj(product_detail) if isinstance(product_detail, dict) else {}
            })
        
        return items
        
    except Exception as e:
        log_error(f"Error getting cart items: {str(e)}")
        return []

@wrap_lambda_handler
def lambda_handler(event, context):
    """
    Lambda handler for GET /cart
    List all items in the user's cart
    """
    correlation_id = event.get('headers', {}).get('x-correlation-id') or event.get('requestContext', {}).get('requestId')
    request_id = context.aws_request_id if context else None
    
    with LoggingContext(correlation_id=correlation_id, request_id=request_id):
        log_info("ListCartFunction invoked", 
                extra_fields={'http_method': event.get('httpMethod'), 
                             'path': event.get('path')})
        
        try:
            # Get user identifier
            pk, is_authenticated = get_user_identifier(event)
            
            log_info(f"User identifier: {pk}, Authenticated: {is_authenticated}")
            
            # Get cart items
            cart_items = get_cart_items(pk)
            
            log_info(f"Retrieved {len(cart_items)} cart items")
            
            # Prepare response
            response = {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
                },
                'body': json.dumps({'products': cart_items})
            }
            
            # Add cart ID header for anonymous users
            if not is_authenticated:
                cart_id = pk.replace('cart#', '')
                response['headers']['X-Cart-ID'] = cart_id
            
            return response
            
        except Exception as e:
            log_error(f"Error in ListCartFunction: {str(e)}")
            return create_error_response(
                status_code=500,
                error_code=ErrorCode.INTERNAL_ERROR,
                message="Failed to list cart items",
                correlation_id=correlation_id,
                request_id=request_id
            )
