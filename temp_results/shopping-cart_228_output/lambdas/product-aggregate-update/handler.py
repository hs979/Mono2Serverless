import os
import json
import boto3
from decimal import Decimal
from botocore.exceptions import ClientError

def _python_obj_to_dynamodb(obj):
    """
    Convert Python objects to DynamoDB-compatible structures.
    Mainly handles float -> Decimal conversion.
    """
    if isinstance(obj, dict):
        return {k: _python_obj_to_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_python_obj_to_dynamodb(item) for item in obj]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj

def update_product_total_quantity(product_id, quantity_change):
    """
    Update product total quantity (incremental update).
    
    Args:
        product_id: Product ID
        quantity_change: Quantity delta (can be positive or negative)
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    pk = f'PRODUCT#{product_id}'
    sk = 'TOTAL'
    
    try:
        # Use atomic ADD
        response = table.update_item(
            Key={'pk': pk, 'sk': sk},
            UpdateExpression='ADD total_quantity :change SET updated_at = :now',
            ExpressionAttributeValues={
                ':change': quantity_change,
                ':now': os.environ.get('AWS_REGION', 'us-east-1')  # Simplified timestamp
            },
            ReturnValues='ALL_NEW'
        )
        
        # If the total becomes < 0, reset to 0
        new_total = response['Attributes'].get('total_quantity', 0)
        if new_total < 0:
            table.update_item(
                Key={'pk': pk, 'sk': sk},
                UpdateExpression='SET total_quantity = :zero',
                ExpressionAttributeValues={':zero': 0}
            )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            # If the record doesn't exist, create it
            initial_total = max(0, quantity_change)
            table.put_item(
                Item={
                    'pk': pk,
                    'sk': sk,
                    'total_quantity': initial_total,
                    'updated_at': os.environ.get('AWS_REGION', 'us-east-1')
                }
            )
        else:
            print(f"Failed to update product aggregate: {e}")
            raise
    except Exception as e:
        print(f"Failed to update product aggregate: {e}")
        raise

def lambda_handler(event, context):
    """
    Internal Lambda handler for updating product aggregate quantities.
    Called by cart-add and cart-update functions.
    """
    try:
        # Parse payload from invoking Lambda
        if 'body' in event:
            # If invoked via API Gateway (testing)
            body = json.loads(event['body'])
        else:
            # If invoked directly via Lambda SDK
            body = event
        
        product_id = body.get('product_id')
        quantity_change = body.get('quantity_change')
        
        if not product_id or quantity_change is None:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Product ID and quantity_change required'})
            }
        
        update_product_total_quantity(product_id, quantity_change)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Product aggregate updated successfully',
                'product_id': product_id,
                'quantity_change': quantity_change
            })
        }
        
    except Exception as e:
        print(f"Error in product-aggregate-update lambda: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error'})
        }
