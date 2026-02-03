"""
用户认证模块
提供JWT token生成和验证，密码加密等功能
"""
import os
import jwt
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash


# JWT配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
ALGORITHM = 'HS256'
TOKEN_EXPIRATION_HOURS = 24


def create_token(user_id, username):
    """
    创建JWT token
    
    Args:
        user_id: 用户ID
        username: 用户名
    
    Returns:
        JWT token字符串
    """
    payload = {
        'sub': user_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_token(token):
    """
    验证JWT token
    
    Args:
        token: JWT token字符串
    
    Returns:
        解码后的payload字典
    
    Raises:
        jwt.ExpiredSignatureError: token已过期
        jwt.InvalidTokenError: token无效
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception('Token has expired')
    except jwt.InvalidTokenError:
        raise Exception('Invalid token')


def hash_password(password):
    """
    加密密码
    
    Args:
        password: 明文密码
    
    Returns:
        加密后的密码哈希
    """
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password, password_hash):
    """
    验证密码
    
    Args:
        password: 明文密码
        password_hash: 密码哈希
    
    Returns:
        布尔值，表示密码是否匹配
    """
    return check_password_hash(password_hash, password)

