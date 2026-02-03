"""
DynamoDB 数据库连接管理
提供数据库客户端和资源对象的访问
"""
import os
import boto3
from flask import g


# DynamoDB配置
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'shopping-cart-monolith')


def get_dynamodb_client():
    """获取DynamoDB客户端（低级API）"""
    client = getattr(g, '_dynamodb_client', None)
    if client is None:
        client = g._dynamodb_client = boto3.client(
            'dynamodb',
            region_name=AWS_REGION
        )
    return client


def get_dynamodb_resource():
    """获取DynamoDB资源对象（高级API）"""
    resource = getattr(g, '_dynamodb_resource', None)
    if resource is None:
        resource = g._dynamodb_resource = boto3.resource(
            'dynamodb',
            region_name=AWS_REGION
        )
    return resource


def get_table():
    """获取购物车主表"""
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(TABLE_NAME)


def close_connection(exception):
    """清理连接（DynamoDB SDK会自动管理连接池，此函数保留用于兼容性）"""
    # 移除缓存的客户端和资源对象
    g.pop('_dynamodb_client', None)
    g.pop('_dynamodb_resource', None)
