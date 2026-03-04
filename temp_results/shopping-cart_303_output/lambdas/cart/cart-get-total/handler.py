import json
import os
import boto3
from decimal import Decimal

# Initialize DynamoDB client
def get_table():
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    return dynamodb.Table(table_name)

def get_product_total_quantity(product_id):
    """
    Get total quantity of a product across all carts.
    
    Args:
        product_id: Product ID
    
    Returns:
        Total quantity
    """
    table = get_table()
    
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
    Returns total quantity of a product across all carts.
    """
    try:
        # Extract product_id from path parameters
        product_id = event['pathParameters']['product_id']
        
        total = get_product_total_quantity(product_id)
        
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
        
    except KeyError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True
            },
            'body': json.dumps({'message': 'Missing product_id in path'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True
            },
            'body': json.dumps({'message': f'Failed to get total: {str(e)}'})
        }