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
    dynamodb_to_python_obj,
    get_current_iso_timestamp
)

# Initialize AWS resources
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

# Get environment variables
CARTS_TABLE_NAME = os.environ.get('CARTS_TABLE')
PRODUCTS_TABLE_NAME = os.environ.get('PRODUCTS_TABLE')
ORDERS_TABLE_NAME = os.environ.get('ORDERS_TABLE')
CHECKOUT_QUEUE_URL = os.environ.get('CHECKOUT_QUEUE_URL')

carts_table = dynamodb.Table(CARTS_TABLE_NAME) if CARTS_TABLE_NAME else None
products_table = dynamodb.Table(PRODUCTS_TABLE_NAME) if PRODUCTS_TABLE_NAME else None
orders_table = dynamodb.Table(ORDERS_TABLE_NAME) if ORDERS_TABLE_NAME else None

def get_user_identifier(event):
    """Get user identifier from the request (authenticated users only for checkout)"""
    auth_header = event.get('headers', {}).get('Authorization') or event.get('headers', {}).get('authorization')
    
    if not auth_header:
        return None, False
    
    try:
        token = auth_header.replace('Bearer ', '')
        # In production, verify JWT token and extract user_id
        user_id = 'demo-user-id'  # From JWT verification
        return f"user#{user_id}", True
    except:
        return None, False

def get_cart_items(pk):
    """Get all items in a cart"""
    if not carts_table:
        return []
    
    try:
        from boto3.dynamodb.conditions import Key
        
        response = carts_table.query(
            KeyConditionExpression=Key('cart_id').eq(pk) & Key('product_id').begins_with('product#')
        )
        
        items = []
        for item in response.get('Items', []):
            product_id = item.get('product_id', '').replace('product#', '')
            quantity = item.get('quantity', 0)
            if isinstance(quantity, Decimal):
                quantity = int(quantity) if quantity % 1 == 0 else float(quantity)
            
            if quantity > 0:
                items.append({
                    'product_id': product_id,
                    'quantity': quantity,
                    'product_detail': dynamodb_to_python_obj(item.get('product_detail', {}))
                })
        
        return items
        
    except Exception as e:
        log_error(f"Error getting cart items: {str(e)}")
        return []

def delete_cart_items(pk):
    """Delete all items in a cart"""
    if not carts_table:
        return False
    
    try:
        from boto3.dynamodb.conditions import Key
        
        # Get all cart items
        response = carts_table.query(
            KeyConditionExpression=Key('cart_id').eq(pk) & Key('product_id').begins_with('product#')
        )
        
        # Batch delete
        with carts_table.batch_writer() as batch:
            for item in response.get('Items', []):
                batch.delete_item(
                    Key={
                        'cart_id': item['cart_id'],
                        'product_id': item['product_id']
                    }
                )
        
        return True
        
    except Exception as e:
        log_error(f"Error deleting cart items: {str(e)}")
        return False

def update_product_total_quantity(product_id, quantity_change):
    """Update product total quantity"""
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

def create_order(user_id, cart_items):
    """Create order record"""
    if not orders_table:
        return None
    
    try:
        import uuid
        order_id = str(uuid.uuid4())
        
        # Calculate total amount
        total_amount = 0
        for item in cart_items:
            product_detail = item.get('product_detail', {})
            price = product_detail.get('price', 0)
            quantity = item.get('quantity', 0)
            total_amount += price * quantity
        
        order = {
            'order_id': order_id,
            'user_id': user_id,
            'cart_id': f"user#{user_id}",
            'total_amount': Decimal(str(total_amount)),
            'status': 'PENDING',
            'items': cart_items,
            'created_at': get_current_iso_timestamp(),
            'updated_at': get_current_iso_timestamp()
        }
        
        orders_table.put_item(Item=order)
        return order_id
        
    except Exception as e:
        log_error(f"Error creating order: {str(e)}")
        return None

def send_to_checkout_queue(order_id, user_id, cart_items):
    """Send checkout message to SQS queue"""
    if not CHECKOUT_QUEUE_URL:
        return False
    
    try:
        message = {
            'order_id': order_id,
            'user_id': user_id,
            'cart_items': cart_items,
            'timestamp': get_current_iso_timestamp()
        }
        
        response = sqs.send_message(
            QueueUrl=CHECKOUT_QUEUE_URL,
            MessageBody=json.dumps(message),
            MessageAttributes={
                'OrderType': {
                    'DataType': 'String',
                    'StringValue': 'CHECKOUT'
                }
            }
        )
        
        log_info(f"Sent message to checkout queue: {response['MessageId']}")
        return True
        
    except Exception as e:
        log_error(f"Error sending to checkout queue: {str(e)}")
        return False

@wrap_lambda_handler
def lambda_handler(event, context):
    """
    Lambda handler for POST /cart/checkout
    Process cart checkout
    """
    correlation_id = event.get('headers', {}).get('x-correlation-id') or event.get('requestContext', {}).get('requestId')
    request_id = context.aws_request_id if context else None
    
    with LoggingContext(correlation_id=correlation_id, request_id=request_id):
        log_info("CheckoutCartFunction invoked", 
                extra_fields={'http_method': event.get('httpMethod'), 
                             'path': event.get('path')})
        
        try:
            # Get user identifier (must be authenticated for checkout)
            pk, is_authenticated = get_user_identifier(event)
            
            if not is_authenticated:
                return create_error_response(
                    status_code=401,
                    error_code=ErrorCode.UNAUTHORIZED,
                    message="Authentication required for checkout",
                    correlation_id=correlation_id,
                    request_id=request_id
                )
            
            user_id = pk.replace('user#', '')
            
            # Get cart items
            cart_items = get_cart_items(pk)
            
            if not cart_items:
                return create_error_response(
                    status_code=400,
                    error_code=ErrorCode.CART_EMPTY,
                    message="Cart is empty",
                    correlation_id=correlation_id,
                    request_id=request_id
                )
            
            log_info(f"Processing checkout for user {user_id} with {len(cart_items)} items")
            
            # Update product total quantities (reduce by cart quantities)
            for item in cart_items:
                product_id = item['product_id']
                quantity = item['quantity']
                update_product_total_quantity(product_id, -quantity)
            
            # Create order record
            order_id = create_order(user_id, cart_items)
            
            if not order_id:
                return create_error_response(
                    status_code=500,
                    error_code=ErrorCode.ORDER_CREATION_FAILED,
                    message="Failed to create order",
                    correlation_id=correlation_id,
                    request_id=request_id
                )
            
            # Send to checkout queue for async processing
            queue_sent = send_to_checkout_queue(order_id, user_id, cart_items)
            
            if not queue_sent:
                log_warning("Failed to send to checkout queue, but order was created")
            
            # Delete cart items
            delete_success = delete_cart_items(pk)
            
            if not delete_success:
                log_warning("Failed to delete cart items, but checkout completed")
            
            # Return success response
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
                },
                'body': json.dumps({
                    'order_id': order_id,
                    'message': 'Checkout successful',
                    'items': cart_items
                })
            }
            
        except Exception as e:
            log_error(f"Error in CheckoutCartFunction: {str(e)}")
            return create_error_response(
                status_code=500,
                error_code=ErrorCode.INTERNAL_ERROR,
                message="Checkout failed",
                correlation_id=correlation_id,
                request_id=request_id
            )
