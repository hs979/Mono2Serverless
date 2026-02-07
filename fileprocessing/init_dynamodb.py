"""
DynamoDB Table Initialization Script
Used to create the DynamoDB table required for the file processing application

Usage:
    python init_dynamodb.py
"""
import boto3
import os
import sys
from botocore.exceptions import ClientError

TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'ref-arch-fileprocessing-sentiment')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

def get_dynamodb_client():
    """Get DynamoDB client"""
    return boto3.client('dynamodb', region_name=AWS_REGION)

def table_exists(client, table_name):
    """Check if the table exists"""
    try:
        client.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            return False
        raise

def wait_for_table(client, table_name):
    """Wait for the table to become ACTIVE"""
    print(f"  Waiting for table {table_name} to become ACTIVE...")
    waiter = client.get_waiter('table_exists')
    waiter.wait(
        TableName=table_name,
        WaiterConfig={
            'Delay': 2,
            'MaxAttempts': 30
        }
    )
    print(f"  ✓ Table {table_name} is ready")

def create_sentiment_table():
    """
    Create sentiment analysis results table
    
    Table Structure:
    - Primary Key: filename (String) - Partition Key
    - Attributes: 
        - last_modified: Last modified time
        - overall_sentiment: Overall sentiment (POSITIVE/NEGATIVE/NEUTRAL/MIXED)
        - positive: Positive sentiment score
        - negative: Negative sentiment score
        - neutral: Neutral sentiment score
        - mixed: Mixed sentiment score
    """
    print('\n========================================')
    print('File Processing App - DynamoDB Table Initialization')
    print('========================================')
    print(f'Region: {AWS_REGION}')
    print(f'Table Name: {TABLE_NAME}')
    print('')
    
    client = get_dynamodb_client()
    
    if table_exists(client, TABLE_NAME):
        print(f'✓ Table already exists: {TABLE_NAME}')
        print('\nHint: Table created, you can use the application directly')
        return
    
    print(f'Creating table: {TABLE_NAME}')
    
    try:
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {
                    'AttributeName': 'filename',
                    'KeyType': 'HASH'  # Partition Key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'filename',
                    'AttributeType': 'S'  # String Type
                }
            ],
            BillingMode='PAY_PER_REQUEST'  # Pay-per-request mode, no throughput specified
        )
        
        wait_for_table(client, TABLE_NAME)
        
        print('\n========================================')
        print('✓ Table initialization completed!')
        print('========================================')
        print(f'\nCreated table:')
        print(f'  - {TABLE_NAME}')
        print(f'    Primary Key: filename (String)')
        print(f'    Billing Mode: PAY_PER_REQUEST')
        print('\nHint: You can start the application now!')
        
    except ClientError as e:
        print(f'\n Failed to create table: {e}')
        
        if e.response['Error']['Code'] == 'UnrecognizedClientException':
            print('Hint: Please check AWS credentials configuration')
            print('  Method 1: aws configure')
            print('  Method 2: Set environment variables AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY')
        elif e.response['Error']['Code'] == 'ResourceInUseException':
            print('Hint: Table already exists')
        
        sys.exit(1)
    except Exception as e:
        print(f'\n Initialization failed: {e}')
        sys.exit(1)

if __name__ == '__main__':
    create_sentiment_table()
