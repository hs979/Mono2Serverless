import json
import os
import boto3
from decimal import Decimal
from datetime import datetime, timedelta
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
    python_obj_to_dynamodb,
    serialize_product_detail,
    generate_ttl,
    get_current_iso_timestamp
)

# Initialize DynamoDB resources
CARTS_TABLE_NAME = os.environ.get('CARTS_TABLE')
PRODUCTS_TABLE_NAME = os.environ.get('PRODUCTS_TABLE')

carts_table = get_table(CARTS_TABLE_NAME) if CARTS_TABLE_NAME else None
products_table = get_table(PRODUCTS_TABLE_NAME) if PRODUCTS_TABLE_NAME else None

# Load product data for validation
import os as _os
_current_dir = _os.path.dirname(_os.path.abspath(__file__))
_product_file = _os.path.join(_current_dir, '..', '..', '..', 'shopping-cart', 'product_list.json')
try:
    with open(_product_file, 'r', encoding='utf-8') as f:
        PRODUCT_LIST = json.load(f)
except:
    PRODUCT_LIST = []

def get_user_identifier(event):
    """Get user identifier from the request"""
    auth_header = event.get('headers', {}).get('Authorization') or event.get('headers', {}).get('authorization')
    
    if auth_header:
        try:
            token = auth_header.replace('Bearer ', '')
            user_id = 'demo-user-id'  # From JWT verification in real app
            return f"user#{user_id}", True
        except:
            pass
    
    cart_id = event.get('headers', {}).get('x-cart-id')
    if not cart_id:
        import uuid
        cart_id = str(uuid.uuid4())
    
    return f"cart#{cart_id}", False, cart_id

def get_product_from_dynamodb(product_id):
    """Get product from DynamoDB"""
    if not products_table:
        return next((p for p in PRODUCT_LIST if p['productId'] == product_id), None)
    
    try:
        response = products_table.get_item(Key={'product_id': product_id})
        if 'Item' in response:
            return dynamodb_to_python_obj(response['Item'])
    except Exception as e:
        log_error(f"Error getting product from DynamoDB: {str(e)}")
    
    return next((p for p in PRODUCT_LIST if p['productId'] == product_id), None)

def add_cart_item(pk, product_id, quantity, product_detail, is_authenticated):
    """Add or update cart item"""
    if not carts_table:
        return False
    
    try:
        # Set expiration time
        if is_authenticated:
            ttl = datetime.now() + timedelta(days=7)
        else:
            ttl = datetime.now() + timedelta(days=1)
        
        # Prepare cart item
        cart_item = {
            'cart_id': pk,
            'product_id': f"product#{product_id}",
            'quantity': Decimal(str(quantity)),
            'product_detail': python_obj_to_dynamodb(product_detail),
            'added_at': get_current_iso_timestamp(),
            'updated_at': get_current_iso_timestamp(),
            'expires_at': ttl.isoformat()
        }
        
        # Add user_id for authenticated users
        if is_authenticated:
            cart_item['user_id'] = pk.replace('user#', '')
        
        # Use UpdateItem for atomic increment
        from boto3.dynamodb.conditions import Attr
        
        response = carts_table.update_item(
            Key={'cart_id': pk, 'product_id': f"product#{product_id}"},
            UpdateExpression="ADD quantity :qty SET product_detail = :detail, added_at = if_not_exists(added_at, :added), updated_at = :updated, expires_at = :expires" + (", user_id = :user_id" if is_authenticated else ""),
            ExpressionAttributeValues={
                ':qty': Decimal(str(quantity)),
                ':detail': python_obj_to_dynamodb(product_detail),
                ':added': get_current_iso_timestamp(),
                ':updated': get_current_iso_timestamp(),
                ':expires': ttl.isoformat(),
                **({':user_id': pk.replace('user#', '')} if is_authenticated else {})
            },
            ReturnValues='ALL_NEW'
        )
        
        # Update product total quantity
        update_product_total_quantity(product_id, quantity)
        
        return True
        
    except Exception as e:
        log_error(f"Error adding cart item: {str(e)}")
        return False

def update_product_total_quantity(product_id, quantity_change):
    """Update product total quantity in DynamoDB"""
    if not products_table:
        return
    
    try:
        products_table.update_item(
            Key={'product_id': product_id},
            UpdateExpression="ADD total_quantity :change SET updated_at = :now",
            ExpressionAttributeValues={
                ':change': Decimal(str(quantity_change)),
                ':now': get_current_iso_timestamp()
            }
        )
    except Exception as e:
        log_error(f"Error updating product total quantity: {str(e)}")

@wrap_lambda_handler
def lambda_handler(event, context):
    """
    Lambda handler for POST /cart
    Add item to cart
    """
    correlation_id = event.get('headers', {}).get('x-correlation-id') or event.get('requestContext', {}).get('requestId')
    request_id = context.aws_request_id if context else None
    
    with LoggingContext(correlation_id=correlation_id, request_id=request_id):
        log_info("AddToCartFunction invoked", 
                extra_fields={'http_method': event.get('httpMethod'), 
                             'path': event.get('path')})
        
        try:
            # Parse request body
            body = json.loads(event.get('body', '{}'))
            product_id = body.get('productId')
            quantity = int(body.get('quantity', 1))
            
            if not product_id:
                return create_error_response(
                    status_code=400,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    message="Product ID is required",
                    correlation_id=correlation_id,
                    request_id=request_id
                )
            
            if quantity <= 0:
                return create_error_response(
                    status_code=400,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    message="Quantity must be positive",
                    correlation_id=correlation_id,
                    request_id=request_id
                )
            
            # Get product details
            product = get_product_from_dynamodb(product_id)
            if not product:
                return create_error_response(
                    status_code=404,
                    error_code=ErrorCode.PRODUCT_NOT_FOUND,
                    message=f"Product with ID '{product_id}' not found",
                    correlation_id=correlation_id,
                    request_id=request_id
                )
            
            # Get user identifier
            pk, is_authenticated, cart_id = get_user_identifier(event)
            
            log_info(f"Adding product to cart: {product_id}, quantity: {quantity}, user: {pk}")
            
            # Add to cart
            success = add_cart_item(pk, product_id, quantity, product, is_authenticated)
            
            if not success:
                return create_error_response(
                    status_code=500,
                    error_code=ErrorCode.INTERNAL_ERROR,
                    message="Failed to add item to cart",
                    correlation_id=correlation_id,
                    request_id=request_id
                )
            
            # Prepare response
            response = {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
                },
                'body': json.dumps({
                    'productId': product_id,
                    'message': 'product added to cart'
                })
            }
            
            # Add cart ID header for anonymous users
            if not is_authenticated:
                response['headers']['X-Cart-ID'] = cart_id
            
            return response
            
        except json.JSONDecodeError:
            return create_error_response(
                status_code=400,
                error_code=ErrorCode.VALIDATION_ERROR,
                message="Invalid JSON body",
                correlation_id=correlation_id,
                request_id=request_id
            )
        except Exception as e:
            log_error(f"Error in AddToCartFunction: {str(e)}")
            return create_error_response(
                status_code=500,
                error_code=ErrorCode.INTERNAL_ERROR,
                message="Failed to add item to cart",
                correlation_id=correlation_id,
                request_id=request_id
            )
