import json
import os
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Attr
from datetime import datetime

# Initialize DynamoDB client
def get_table():
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    return dynamodb.Table(table_name)

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

def get_all_products():
    """
    Get all products from DynamoDB.

    Returns:
        List of product dicts
    """
    table = get_table()
    products = []

    try:
        scan_kwargs = {
            'FilterExpression': Attr('pk').begins_with('PRODUCT#') & Attr('sk').eq('DETAIL')
        }

        while True:
            response = table.scan(**scan_kwargs)
            for item in response.get('Items', []):
                product = _dynamodb_to_python_obj(item)
                product.pop('pk', None)
                product.pop('sk', None)
                products.append(product)

            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break
            scan_kwargs['ExclusiveStartKey'] = last_key

        return products
    except Exception as e:
        print(f"Failed to get products: {e}")
        return []

def lambda_handler(event, context):
    """
    Lambda handler for GET /product endpoint.
    Returns all products.
    """
    try:
        products = get_all_products()
        
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
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True
            },
            'body': json.dumps({'message': f'Internal server error: {str(e)}'})
        }