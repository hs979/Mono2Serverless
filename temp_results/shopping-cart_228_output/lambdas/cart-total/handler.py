import os
import json
import boto3
from decimal import Decimal

def _dynamodb_to_python_obj(obj):
    """
    Convert DynamoDB objects to standard Python objects.
    Mainly handles Decimal -> int/float conversion.
    """
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

def get_product_total_quantity(product_id):
    """
    Get total quantity of a product across all carts.
    
    Args:
        product_id: Product ID
    
    Returns:
        Total quantity
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    try:
        response = table.get_item(
            Key={
                'pk': f'PRODUCT#{product_id}',
                'sk': 'TOTAL'
            }
        )
        
        if 'Item' in response:
            total = response['Item'].get('total_quantity', 0)
            return int(total) if isinstance(total, Decimal) else total
        return 0
    except Exception as e:
        print(f"Failed to get product aggregate: {e}")
        return 0

def lambda_handler(event, context):
    """
    Lambda handler for GET /cart/{product_id}/total endpoint.
    Get total quantity of a product across all carts.
    """
    try:
        # Extract product_id from path parameters
        product_id = event.get('pathParameters', {}).get('product_id')
        
        if not product_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Product ID required'})
            }
        
        total = get_product_total_quantity(product_id)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'product': product_id,
                'quantity': total
            })
        }
        
    except Exception as e:
        print(f"Error in cart-total lambda: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Internal server error'})
        }
