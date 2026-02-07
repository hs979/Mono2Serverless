"""
Database utilities for DynamoDB operations
"""

import os
import boto3
from decimal import Decimal
import json
from datetime import datetime
from typing import Any, Dict, List, Union


def get_dynamodb_resource():
    """Get DynamoDB resource object"""
    region = os.environ.get('AWS_REGION', 'us-east-1')
    return boto3.resource('dynamodb', region_name=region)


def get_dynamodb_client():
    """Get DynamoDB client"""
    region = os.environ.get('AWS_REGION', 'us-east-1')
    return boto3.client('dynamodb', region_name=region)


def get_table(table_name: str):
    """Get DynamoDB table"""
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(table_name)


def python_obj_to_dynamodb(obj: Any) -> Any:
    """
    Convert Python object to DynamoDB compatible format
    Mainly handles float to Decimal conversion
    """
    if isinstance(obj, dict):
        return {k: python_obj_to_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [python_obj_to_dynamodb(item) for item in obj]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, int):
        return Decimal(str(obj))
    else:
        return obj


def dynamodb_to_python_obj(obj: Any) -> Any:
    """
    Convert DynamoDB object to Python standard object
    Mainly handles Decimal to int/float conversion
    """
    if isinstance(obj, dict):
        return {k: dynamodb_to_python_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [dynamodb_to_python_obj(item) for item in obj]
    elif isinstance(obj, Decimal):
        # If it's an integer, return int; otherwise return float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj


def serialize_product_detail(product_detail: Dict[str, Any]) -> str:
    """Serialize product detail to JSON string"""
    return json.dumps(python_obj_to_dynamodb(product_detail))


def deserialize_product_detail(product_detail_str: str) -> Dict[str, Any]:
    """Deserialize product detail from JSON string"""
    if not product_detail_str:
        return {}
    try:
        return json.loads(product_detail_str)
    except:
        return {}


def generate_ttl(expiration_time: datetime) -> int:
    """Generate TTL timestamp from datetime"""
    return int(expiration_time.timestamp())


def get_current_iso_timestamp() -> str:
    """Get current ISO format timestamp"""
    return datetime.now().isoformat()
