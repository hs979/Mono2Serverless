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
        # If it's an integer, return int; otherwise return float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj

def get_product_by_id(product_id):
    """
    Get product detail by product ID from DynamoDB.

    Args:
        product_id: Product ID

    Returns:
        Product dict or None
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    try:
        response = table.get_item(
            Key={
                'pk': f'PRODUCT#{product_id}',
                'sk': 'DETAIL'
            }
        )
        item = response.get('Item')
        if not item:
            return None

        product = _dynamodb_to_python_obj(item)
        product.pop('pk', None)
        product.pop('sk', None)
        return product
    except Exception as e:
        print(f"Failed to get product {product_id}: {e}")
        return None

def lambda_handler(event, context):
    """
    Lambda handler for GET /product/{product_id} endpoint.
    Returns product details by product_id.
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
        
        product = get_product_by_id(product_id)
        
        if not product:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Product not found'})
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'product': product})
        }
    except Exception as e:
        print(f"Error in products-get lambda: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Internal server error'})
        }
