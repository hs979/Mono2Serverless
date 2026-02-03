"""
DynamoDB表初始化脚本
创建购物车应用所需的DynamoDB表

使用方法：
  python init_dynamodb.py
"""
import os
import sys
import boto3
from botocore.exceptions import ClientError


# DynamoDB配置
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'shopping-cart-monolith')


def get_dynamodb_resource():
    """获取DynamoDB资源对象"""
    return boto3.resource(
        'dynamodb',
        region_name=AWS_REGION
    )


def init_dynamodb():
    """
    初始化DynamoDB表结构
    创建一个单表设计，用于存储用户、购物车和商品统计数据
    """
    dynamodb = get_dynamodb_resource()
    
    try:
        # 检查表是否已存在
        existing_tables = dynamodb.meta.client.list_tables()['TableNames']
        if TABLE_NAME in existing_tables:
            print(f"表 {TABLE_NAME} 已存在，跳过创建")
            return
        
        # 创建主表 - 使用单表设计
        # pk (Partition Key) 和 sk (Sort Key) 用于区分不同类型的数据：
        # - 用户: pk='USER#{username}', sk='PROFILE'
        # - 购物车项: pk='user#{userId}' 或 'cart#{cartId}', sk='product#{productId}'
        # - 商品统计: pk='PRODUCT#{productId}', sk='TOTAL'
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'pk', 'KeyType': 'HASH'},   # Partition key
                {'AttributeName': 'sk', 'KeyType': 'RANGE'}   # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'pk', 'AttributeType': 'S'},
                {'AttributeName': 'sk', 'AttributeType': 'S'},
                {'AttributeName': 'username', 'AttributeType': 'S'}  # GSI
            ],
            # 添加全局二级索引用于通过username查询用户
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'username-index',
                    'KeySchema': [
                        {'AttributeName': 'username', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        
        # 等待表创建完成
        print(f"正在创建表 {TABLE_NAME}...")
        table.meta.client.get_waiter('table_exists').wait(TableName=TABLE_NAME)
        print(f"表 {TABLE_NAME} 创建成功！")
        
        # 启用TTL（用于自动清理过期的购物车项）
        try:
            dynamodb.meta.client.update_time_to_live(
                TableName=TABLE_NAME,
                TimeToLiveSpecification={
                    'Enabled': True,
                    'AttributeName': 'expirationTime'
                }
            )
            print(f"表 {TABLE_NAME} 的TTL已启用")
        except Exception as e:
            print(f"启用TTL时出错（可忽略）: {e}")
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"表 {TABLE_NAME} 已存在")
        else:
            print(f"创建表时出错: {e}")
            raise
    except Exception as e:
        print(f"初始化DynamoDB时出错: {e}")
        raise


def main():
    """主函数"""
    print('========================================')
    print('购物车应用 - DynamoDB表初始化')
    print('========================================')
    print(f'区域: {AWS_REGION}')
    print('')
    
    try:
        init_dynamodb()
        
        print('')
        print('========================================')
        print('✓ 数据库初始化完成！')
        print('========================================')
        print('')
        print('创建的表:')
        print(f'  1. {TABLE_NAME} - 购物车主表（单表设计）')
        print('')
        print('现在可以启动应用了:')
        print('  python app.py')
        print('')
        
    except Exception as e:
        print('')
        print('========================================')
        print('✗ 初始化失败！')
        print('========================================')
        print(f'错误信息: {e}')
        print('')
        sys.exit(1)


if __name__ == '__main__':
    main()
