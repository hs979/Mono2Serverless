"""
购物车单体应用 - 主应用文件
提供产品查询和购物车管理的RESTful API
"""
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from uuid import uuid4

from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS

from db import close_connection
from init_dynamodb import init_dynamodb
from auth import create_token, verify_token, hash_password, verify_password
from models import (
    get_cart_items,
    add_cart_item,
    update_cart_item_quantity,
    delete_cart_items,
    get_product_total_quantity,
    update_product_total_quantity,
    migrate_cart_items,
    create_user,
    get_user_by_username
)

# 初始化Flask应用
# 配置静态文件目录为frontend/dist
app = Flask(__name__,
            static_folder='frontend/dist',
            static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app, supports_credentials=True)

# 加载产品数据
import os as _os
_current_dir = _os.path.dirname(_os.path.abspath(__file__))
_product_file = _os.path.join(_current_dir, 'product_list.json')
with open(_product_file, 'r', encoding='utf-8') as f:
    PRODUCT_LIST = json.load(f)

# 初始化DynamoDB数据库
with app.app_context():
    init_dynamodb()

# 注册teardown函数，用于清理连接
app.teardown_appcontext(close_connection)


def get_cart_id_from_cookie():
    """从Cookie中获取购物车ID，如果不存在则生成新的"""
    cart_id = request.cookies.get('cartId')
    generated = False
    if not cart_id:
        cart_id = str(uuid4())
        generated = True
    return cart_id, generated


def set_cart_cookie(response, cart_id):
    """设置购物车Cookie"""
    response.set_cookie(
        'cartId',
        cart_id,
        max_age=60 * 60 * 24,  # 1天
        secure=False,  # 开发环境设为False，生产环境应为True
        httponly=True,
        samesite='Lax',
        path='/'
    )
    return response


def login_required(f):
    """认证装饰器 - 要求用户登录"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'message': 'Missing authorization header'}), 401
        
        try:
            # 支持 "Bearer token" 或直接 "token" 格式
            token = auth_header.replace('Bearer ', '')
            payload = verify_token(token)
            request.user_id = payload['sub']
            request.username = payload['username']
        except Exception as e:
            return jsonify({'message': 'Invalid or expired token'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_user_identifier():
    """获取用户标识（已登录用户的user_id或匿名用户的cart_id）"""
    auth_header = request.headers.get('Authorization')
    if auth_header:
        try:
            token = auth_header.replace('Bearer ', '')
            payload = verify_token(token)
            return f"user#{payload['sub']}", True
        except:
            pass
    
    cart_id, _ = get_cart_id_from_cookie()
    return f"cart#{cart_id}", False


# ==================== 用户认证相关API ====================

@app.route('/auth/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    if not username or not password:
        return jsonify({'message': 'Username and password required'}), 400
    
    # 检查用户是否已存在
    if get_user_by_username(username):
        return jsonify({'message': 'Username already exists'}), 400
    
    # 创建用户
    user_id = create_user(username, password, email)
    
    return jsonify({
        'message': 'User registered successfully',
        'userId': user_id
    }), 201


@app.route('/auth/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'message': 'Username and password required'}), 400
    
    # 验证用户
    user = get_user_by_username(username)
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    # 生成JWT token
    token = create_token(user['id'], username)
    
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'userId': user['id'],
        'username': username
    }), 200


# ==================== 产品相关API ====================

@app.route('/product', methods=['GET'])
def get_products():
    """获取所有产品列表"""
    return jsonify({'products': PRODUCT_LIST}), 200


@app.route('/product/<product_id>', methods=['GET'])
def get_product(product_id):
    """获取单个产品详情"""
    product = next((p for p in PRODUCT_LIST if p['productId'] == product_id), None)
    
    if not product:
        return jsonify({'message': 'Product not found'}), 404
    
    return jsonify({'product': product}), 200


# ==================== 购物车相关API ====================

@app.route('/cart', methods=['GET'])
def list_cart():
    """获取当前用户的购物车内容"""
    cart_id, generated = get_cart_id_from_cookie()
    pk, is_authenticated = get_user_identifier()
    
    # 如果是新生成的cart_id，不需要查询数据库
    if generated and not is_authenticated:
        product_list = []
    else:
        product_list = get_cart_items(pk)
    
    # 清理返回数据格式
    for product in product_list:
        if 'sk' in product:
            product['sk'] = product['sk'].replace('product#', '')
    
    response = make_response(jsonify({'products': product_list}))
    response = set_cart_cookie(response, cart_id)
    return response, 200


@app.route('/cart', methods=['POST'])
def add_to_cart():
    """添加商品到购物车"""
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No request payload'}), 400
    
    product_id = data.get('productId')
    quantity = data.get('quantity', 1)
    
    if not product_id:
        return jsonify({'message': 'Product ID required'}), 400
    
    # 验证产品是否存在
    product = next((p for p in PRODUCT_LIST if p['productId'] == product_id), None)
    if not product:
        return jsonify({'message': 'Product not found'}), 404
    
    cart_id, _ = get_cart_id_from_cookie()
    pk, is_authenticated = get_user_identifier()
    
    # 设置过期时间
    if is_authenticated:
        ttl = datetime.now() + timedelta(days=7)
    else:
        ttl = datetime.now() + timedelta(days=1)
    
    # 添加或更新购物车项
    try:
        add_cart_item(pk, product_id, quantity, product, ttl)
        # 同步更新商品统计
        update_product_total_quantity(product_id, quantity)
    except Exception as e:
        return jsonify({'message': f'Failed to add to cart: {str(e)}'}), 500
    
    response = make_response(jsonify({
        'productId': product_id,
        'message': 'product added to cart'
    }))
    response = set_cart_cookie(response, cart_id)
    return response, 200


@app.route('/cart/<product_id>', methods=['PUT'])
def update_cart(product_id):
    """更新购物车中指定商品的数量（幂等操作）"""
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No request payload'}), 400
    
    quantity = int(data.get('quantity', 0))
    
    if quantity < 0:
        return jsonify({
            'productId': product_id,
            'message': 'Quantity must not be lower than 0'
        }), 400
    
    # 验证产品是否存在
    product = next((p for p in PRODUCT_LIST if p['productId'] == product_id), None)
    if not product:
        return jsonify({'message': 'Product not found'}), 404
    
    cart_id, _ = get_cart_id_from_cookie()
    pk, is_authenticated = get_user_identifier()
    
    # 设置过期时间
    if is_authenticated:
        ttl = datetime.now() + timedelta(days=7)
    else:
        ttl = datetime.now() + timedelta(days=1)
    
    try:
        # 获取旧的数量以计算差值
        old_quantity = 0
        items = get_cart_items(pk)
        for item in items:
            if item['sk'] == f"product#{product_id}":
                old_quantity = item['quantity']
                break
        
        # 更新购物车项
        update_cart_item_quantity(pk, product_id, quantity, product, ttl)
        
        # 同步更新商品统计（差值）
        quantity_diff = quantity - old_quantity
        if quantity_diff != 0:
            update_product_total_quantity(product_id, quantity_diff)
    except Exception as e:
        return jsonify({'message': f'Failed to update cart: {str(e)}'}), 500
    
    response = make_response(jsonify({
        'productId': product_id,
        'quantity': quantity,
        'message': 'cart updated'
    }))
    response = set_cart_cookie(response, cart_id)
    return response, 200


@app.route('/cart/migrate', methods=['POST'])
@login_required
def migrate_cart():
    """将匿名购物车迁移到已登录用户账户"""
    cart_id, _ = get_cart_id_from_cookie()
    user_id = request.user_id
    
    anonymous_pk = f"cart#{cart_id}"
    user_pk = f"user#{user_id}"
    
    try:
        # 迁移购物车项
        migrated_items = migrate_cart_items(anonymous_pk, user_pk)
    except Exception as e:
        return jsonify({'message': f'Failed to migrate cart: {str(e)}'}), 500
    
    # 获取迁移后的购物车
    product_list = get_cart_items(user_pk)
    
    # 清理返回数据格式
    for product in product_list:
        if 'sk' in product:
            product['sk'] = product['sk'].replace('product#', '')
    
    response = make_response(jsonify({'products': product_list}))
    response = set_cart_cookie(response, cart_id)
    return response, 200


@app.route('/cart/checkout', methods=['POST'])
@login_required
def checkout_cart():
    """结算购物车（清空购物车）"""
    cart_id, _ = get_cart_id_from_cookie()
    user_id = request.user_id
    user_pk = f"user#{user_id}"
    
    # 获取购物车项
    cart_items = get_cart_items(user_pk)
    
    try:
        # 清空购物车前，需要更新商品统计（减少数量）
        for item in cart_items:
            product_id = item['sk'].replace('product#', '')
            quantity = -item['quantity']  # 负数表示减少
            update_product_total_quantity(product_id, quantity)
        
        # 删除购物车项
        delete_cart_items(user_pk)
    except Exception as e:
        return jsonify({'message': f'Failed to checkout: {str(e)}'}), 500
    
    response = make_response(jsonify({
        'products': cart_items,
        'message': 'Checkout successful'
    }))
    response = set_cart_cookie(response, cart_id)
    return response, 200


@app.route('/cart/<product_id>/total', methods=['GET'])
def get_cart_total(product_id):
    """获取指定商品在所有购物车中的总数量"""
    try:
        total = get_product_total_quantity(product_id)
    except Exception as e:
        return jsonify({'message': f'Failed to get total: {str(e)}'}), 500
    
    return jsonify({
        'product': product_id,
        'quantity': total
    }), 200


# ==================== 前端静态文件托管 ====================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """
    服务前端静态文件
    所有非API路由都返回index.html，由前端Vue Router处理
    """
    # API路由不应该被这里处理
    if path.startswith('auth/') or path.startswith('cart') or path.startswith('product'):
        return jsonify({'message': 'API endpoint not found'}), 404
    
    # 如果请求的是静态资源文件（有扩展名），尝试返回该文件
    if path and '.' in path:
        try:
            return send_from_directory(app.static_folder, path)
        except:
            pass
    
    # 否则返回index.html，让前端路由处理
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except:
        return jsonify({'message': 'Frontend not built. Please run: cd frontend && npm install && npm run build'}), 404


# ==================== 错误处理 ====================

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    return jsonify({'message': 'Internal server error'}), 500


# ==================== 应用入口 ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

