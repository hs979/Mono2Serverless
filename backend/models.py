"""
数据模型和数据库操作
提供用户、购物车、商品统计等数据的CRUD操作
使用DynamoDB作为数据存储
"""
import json
from uuid import uuid4
from datetime import datetime, timedelta
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from db import get_table
from auth import hash_password


# ==================== 辅助函数 ====================

def _python_obj_to_dynamodb(obj):
    """
    将Python对象转换为DynamoDB兼容的格式
    主要处理float到Decimal的转换
    """
    if isinstance(obj, dict):
        return {k: _python_obj_to_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_python_obj_to_dynamodb(item) for item in obj]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def _dynamodb_to_python_obj(obj):
    """
    将DynamoDB对象转换为Python标准对象
    主要处理Decimal到float的转换
    """
    if isinstance(obj, dict):
        return {k: _dynamodb_to_python_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_dynamodb_to_python_obj(item) for item in obj]
    elif isinstance(obj, Decimal):
        # 如果是整数，返回int；否则返回float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj


# ==================== 用户相关操作 ====================

def create_user(username, password, email=None):
    """
    创建新用户
    
    Args:
        username: 用户名
        password: 明文密码
        email: 邮箱（可选）
    
    Returns:
        用户ID
    """
    table = get_table()
    user_id = str(uuid4())
    password_hash = hash_password(password)
    
    # 用户记录: pk='USER#{username}', sk='PROFILE'
    item = {
        'pk': f'USER#{username}',
        'sk': 'PROFILE',
        'id': user_id,
        'username': username,
        'password_hash': password_hash,
        'email': email,
        'created_at': datetime.now().isoformat()
    }
    
    try:
        # 使用条件表达式确保用户名唯一
        table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(pk)'
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise Exception(f'用户名 {username} 已存在')
        raise
    
    return user_id


def get_user_by_username(username):
    """
    根据用户名获取用户信息
    
    Args:
        username: 用户名
    
    Returns:
        用户字典或None
    """
    table = get_table()
    
    try:
        response = table.get_item(
            Key={
                'pk': f'USER#{username}',
                'sk': 'PROFILE'
            }
        )
        
        if 'Item' in response:
            return _dynamodb_to_python_obj(response['Item'])
        return None
    except Exception as e:
        print(f"获取用户失败: {e}")
        return None


def get_user_by_id(user_id):
    """
    根据用户ID获取用户信息
    
    Args:
        user_id: 用户ID
    
    Returns:
        用户字典或None
    """
    table = get_table()
    
    # 由于我们使用username作为主键的一部分，需要扫描表
    # 在生产环境中，建议添加GSI来优化这个查询
    try:
        response = table.scan(
            FilterExpression=Attr('id').eq(user_id) & Attr('sk').eq('PROFILE')
        )
        
        if response['Items']:
            return _dynamodb_to_python_obj(response['Items'][0])
        return None
    except Exception as e:
        print(f"获取用户失败: {e}")
        return None


# ==================== 购物车相关操作 ====================

def get_cart_items(pk):
    """
    获取购物车中的所有商品
    
    Args:
        pk: 主键（user#xxx 或 cart#xxx）
    
    Returns:
        商品列表
    """
    table = get_table()
    
    try:
        # 查询购物车项，只获取product#开头的项
        response = table.query(
            KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('product#')
        )
        
        items = []
        current_time = datetime.now()
        
        for item in response['Items']:
            # 过滤掉数量为0和已过期的项
            quantity = item.get('quantity', 0)
            if quantity <= 0:
                continue
            
            # 检查是否过期
            expiration_time = item.get('expirationTime')
            if expiration_time:
                # DynamoDB的TTL是Unix时间戳（秒）
                # 需要将Decimal转换为int或float
                if isinstance(expiration_time, Decimal):
                    expiration_time = int(expiration_time)
                exp_datetime = datetime.fromtimestamp(expiration_time)
                if exp_datetime < current_time:
                    continue
            
            # 解析product_detail
            product_detail = item.get('product_detail')
            if product_detail and isinstance(product_detail, str):
                product_detail = json.loads(product_detail)
            
            items.append({
                'sk': item['sk'],
                'quantity': int(quantity) if isinstance(quantity, Decimal) else quantity,
                'productDetail': _dynamodb_to_python_obj(product_detail)
            })
        
        return items
    except Exception as e:
        print(f"获取购物车失败: {e}")
        return []


def add_cart_item(pk, product_id, quantity, product_detail, expiration_time):
    """
    添加或更新购物车项（增加数量）
    
    Args:
        pk: 主键（user#xxx 或 cart#xxx）
        product_id: 产品ID
        quantity: 数量（可以是负数）
        product_detail: 产品详情字典
        expiration_time: 过期时间（datetime对象）
    """
    table = get_table()
    sk = f"product#{product_id}"
    
    # 转换过期时间为Unix时间戳（DynamoDB TTL格式）
    ttl = int(expiration_time.timestamp()) if expiration_time else None
    
    # 转换product_detail为JSON字符串
    product_detail_json = json.dumps(_python_obj_to_dynamodb(product_detail))
    
    try:
        # 使用UpdateItem实现原子性的增量更新
        response = table.update_item(
            Key={'pk': pk, 'sk': sk},
            UpdateExpression='ADD quantity :qty SET product_detail = :detail, expirationTime = :ttl, updated_at = :now',
            ExpressionAttributeValues={
                ':qty': quantity,
                ':detail': product_detail_json,
                ':ttl': ttl,
                ':now': datetime.now().isoformat()
            },
            ReturnValues='ALL_NEW'
        )
        
        # 如果更新后数量小于等于0，删除该项
        new_quantity = response['Attributes'].get('quantity', 0)
        if new_quantity <= 0:
            table.delete_item(Key={'pk': pk, 'sk': sk})
            
    except Exception as e:
        print(f"添加购物车项失败: {e}")
        raise


def update_cart_item_quantity(pk, product_id, quantity, product_detail, expiration_time):
    """
    更新购物车项数量（幂等操作，直接设置为指定数量）
    
    Args:
        pk: 主键（user#xxx 或 cart#xxx）
        product_id: 产品ID
        quantity: 数量
        product_detail: 产品详情字典
        expiration_time: 过期时间（datetime对象）
    """
    table = get_table()
    sk = f"product#{product_id}"
    
    # 转换过期时间为Unix时间戳
    ttl = int(expiration_time.timestamp()) if expiration_time else None
    
    # 转换product_detail为JSON字符串
    product_detail_json = json.dumps(_python_obj_to_dynamodb(product_detail))
    
    try:
        if quantity <= 0:
            # 数量为0或负数，删除该项
            table.delete_item(Key={'pk': pk, 'sk': sk})
        else:
            # 直接设置数量
            table.put_item(
                Item={
                    'pk': pk,
                    'sk': sk,
                    'quantity': quantity,
                    'product_detail': product_detail_json,
                    'expirationTime': ttl,
                    'updated_at': datetime.now().isoformat()
                }
            )
    except Exception as e:
        print(f"更新购物车项失败: {e}")
        raise


def delete_cart_items(pk):
    """
    删除指定用户/购物车的所有商品
    
    Args:
        pk: 主键（user#xxx 或 cart#xxx）
    """
    table = get_table()
    
    try:
        # 先查询所有购物车项
        response = table.query(
            KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('product#')
        )
        
        # 批量删除
        with table.batch_writer() as batch:
            for item in response['Items']:
                batch.delete_item(
                    Key={
                        'pk': item['pk'],
                        'sk': item['sk']
                    }
                )
    except Exception as e:
        print(f"删除购物车项失败: {e}")
        raise


def migrate_cart_items(anonymous_pk, user_pk):
    """
    将匿名购物车迁移到用户账户
    
    Args:
        anonymous_pk: 匿名购物车主键（cart#xxx）
        user_pk: 用户主键（user#xxx）
    
    Returns:
        迁移的商品列表
    """
    table = get_table()
    
    try:
        # 获取匿名购物车的所有商品
        response = table.query(
            KeyConditionExpression=Key('pk').eq(anonymous_pk) & Key('sk').begins_with('product#')
        )
        
        anonymous_items = response['Items']
        migrated_items = []
        
        # 迁移到用户账户
        for item in anonymous_items:
            sk = item['sk']
            quantity = item.get('quantity', 0)
            # 处理Decimal类型
            if isinstance(quantity, Decimal):
                quantity = int(quantity)
            product_detail = item.get('product_detail')
            
            if quantity <= 0:
                continue
            
            # 设置新的过期时间（已登录用户保留30天）
            expiration_time = datetime.now() + timedelta(days=30)
            ttl = int(expiration_time.timestamp())
            
            # 检查用户购物车是否已有此商品
            try:
                user_response = table.get_item(Key={'pk': user_pk, 'sk': sk})
                
                if 'Item' in user_response:
                    # 已存在则累加数量（使用原子性ADD操作）
                    table.update_item(
                        Key={'pk': user_pk, 'sk': sk},
                        UpdateExpression='ADD quantity :qty SET product_detail = :detail, expirationTime = :ttl, updated_at = :now',
                        ExpressionAttributeValues={
                            ':qty': quantity,
                            ':detail': product_detail,
                            ':ttl': ttl,
                            ':now': datetime.now().isoformat()
                        }
                    )
                else:
                    # 不存在则插入
                    table.put_item(
                        Item={
                            'pk': user_pk,
                            'sk': sk,
                            'quantity': quantity,
                            'product_detail': product_detail,
                            'expirationTime': ttl,
                            'updated_at': datetime.now().isoformat()
                        }
                    )
            except Exception as e:
                print(f"迁移商品 {sk} 失败: {e}")
                continue
            
            migrated_items.append({
                'sk': sk,
                'quantity': quantity,
                'product_detail': product_detail
            })
        
        # 删除匿名购物车的商品
        delete_cart_items(anonymous_pk)
        
        return migrated_items
        
    except Exception as e:
        print(f"迁移购物车失败: {e}")
        raise


# ==================== 商品统计相关操作 ====================

def get_product_total_quantity(product_id):
    """
    获取指定商品在所有购物车中的总数量
    
    Args:
        product_id: 产品ID
    
    Returns:
        总数量
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
        print(f"获取商品统计失败: {e}")
        return 0


def update_product_total_quantity(product_id, quantity_change):
    """
    更新商品的总数量统计（增量更新）
    
    Args:
        product_id: 产品ID
        quantity_change: 数量变化（可以是正数或负数）
    """
    table = get_table()
    pk = f'PRODUCT#{product_id}'
    sk = 'TOTAL'
    
    try:
        # 使用原子性的ADD操作
        response = table.update_item(
            Key={'pk': pk, 'sk': sk},
            UpdateExpression='ADD total_quantity :change SET updated_at = :now',
            ExpressionAttributeValues={
                ':change': quantity_change,
                ':now': datetime.now().isoformat()
            },
            ReturnValues='ALL_NEW'
        )
        
        # 如果总数小于0，重置为0
        new_total = response['Attributes'].get('total_quantity', 0)
        if new_total < 0:
            table.update_item(
                Key={'pk': pk, 'sk': sk},
                UpdateExpression='SET total_quantity = :zero',
                ExpressionAttributeValues={':zero': 0}
            )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            # 如果记录不存在，创建新记录
            initial_total = max(0, quantity_change)
            table.put_item(
                Item={
                    'pk': pk,
                    'sk': sk,
                    'total_quantity': initial_total,
                    'updated_at': datetime.now().isoformat()
                }
            )
        else:
            print(f"更新商品统计失败: {e}")
            raise
    except Exception as e:
        print(f"更新商品统计失败: {e}")
        raise


# ==================== 数据清理 ====================

def cleanup_expired_items():
    """
    清理过期的购物车项
    注意：DynamoDB的TTL会自动清理过期项，此函数作为备用手动清理
    """
    table = get_table()
    current_timestamp = int(datetime.now().timestamp())
    
    try:
        # 扫描所有过期的购物车项
        response = table.scan(
            FilterExpression=Attr('expirationTime').exists() & Attr('expirationTime').lt(current_timestamp)
        )
        
        deleted_count = 0
        with table.batch_writer() as batch:
            for item in response['Items']:
                batch.delete_item(
                    Key={
                        'pk': item['pk'],
                        'sk': item['sk']
                    }
                )
                deleted_count += 1
        
        return deleted_count
    except Exception as e:
        print(f"清理过期项失败: {e}")
        return 0
