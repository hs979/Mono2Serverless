#!/usr/bin/env python3
"""
产品数据加载脚本
将product_list.json中的产品数据加载到DynamoDB（可选）
注意：当前应用从JSON文件读取产品，此脚本为未来扩展预留
"""
import json
import os
from datetime import datetime
from db import get_table


def load_products_to_dynamodb():
    """
    将产品数据加载到DynamoDB
    产品记录格式: pk='PRODUCT#{productId}', sk='DETAIL'
    """
    # 读取产品数据
    current_dir = os.path.dirname(os.path.abspath(__file__))
    product_file = os.path.join(current_dir, 'product_list.json')
    
    print(f"正在读取产品数据: {product_file}")
    with open(product_file, 'r', encoding='utf-8') as f:
        products = json.load(f)
    
    print(f"找到 {len(products)} 个产品")
    
    # 获取DynamoDB表
    table = get_table()
    
    # 批量写入产品数据
    print("开始写入DynamoDB...")
    with table.batch_writer() as batch:
        for product in products:
            product_id = product['productId']
            
            # 产品详情记录
            item = {
                'pk': f'PRODUCT#{product_id}',
                'sk': 'DETAIL',
                'productId': product_id,
                'name': product.get('name', ''),
                'price': product.get('price', 0),
                'description': product.get('description', ''),
                'picture': product.get('picture', ''),
                'created_at': datetime.now().isoformat()
            }
            
            batch.put_item(Item=item)
            print(f"  - 已加载: {product.get('name', product_id)}")
    
    print(f"\n✓ 成功加载 {len(products)} 个产品到DynamoDB！")


if __name__ == '__main__':
    print("=" * 60)
    print("产品数据加载脚本")
    print("=" * 60)
    print("\n注意：当前应用直接从product_list.json读取产品数据")
    print("此脚本用于将产品数据加载到DynamoDB（可选操作）")
    print("\n如果您希望从DynamoDB读取产品，需要修改app.py中的产品相关接口\n")
    
    try:
        load_products_to_dynamodb()
    except Exception as e:
        print(f"\n✗ 加载失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

