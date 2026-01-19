import axios from 'axios'

// 配置axios基础URL（开发环境代理到后端，生产环境使用相对路径）
const apiClient = axios.create({
    baseURL: process.env.VUE_APP_API_BASE_URL || '',
    withCredentials: true,
    headers: {
        'Content-Type': 'application/json'
    }
})

// 请求拦截器 - 自动添加认证token
apiClient.interceptors.request.use(
    config => {
        const token = localStorage.getItem('authToken')
        if (token) {
            config.headers['Authorization'] = `Bearer ${token}`
        }
        return config
    },
    error => {
        return Promise.reject(error)
    }
)

// 响应拦截器 - 处理401错误
apiClient.interceptors.response.use(
    response => response,
    error => {
        if (error.response && error.response.status === 401) {
            // Token过期或无效，清除本地存储
            localStorage.removeItem('authToken')
            localStorage.removeItem('user')
            // 可以选择重定向到登录页
            // window.location.href = '/auth'
        }
        return Promise.reject(error)
    }
)

// 认证相关API
export async function register(username, password, email) {
    const response = await apiClient.post('/auth/register', {
        username,
        password,
        email
    })
    return response.data
}

export async function login(username, password) {
    const response = await apiClient.post('/auth/login', {
        username,
        password
    })
    
    // 保存token和用户信息
    if (response.data.token) {
        localStorage.setItem('authToken', response.data.token)
        localStorage.setItem('user', JSON.stringify({
            userId: response.data.userId,
            username: response.data.username
        }))
    }
    
    return response.data
}

export function logout() {
    localStorage.removeItem('authToken')
    localStorage.removeItem('user')
}

export function getCurrentUser() {
    const userStr = localStorage.getItem('user')
    return userStr ? JSON.parse(userStr) : null
}

export function isAuthenticated() {
    return !!localStorage.getItem('authToken')
}

// 购物车相关API
export async function getCart() {
    const response = await apiClient.get('/cart')
    return response.data
}

export async function postCart(obj, quantity = 1) {
    const response = await apiClient.post('/cart', {
        productId: obj.productId,
        quantity: quantity
    })
    return response.data
}

export async function putCart(obj, quantity) {
    const response = await apiClient.put(`/cart/${obj.productId}`, {
        quantity: quantity
    })
    return response.data
}

export async function cartMigrate() {
    const response = await apiClient.post('/cart/migrate')
    return response.data
}

export async function cartCheckout() {
    const response = await apiClient.post('/cart/checkout')
    return response.data
}

// 产品相关API
export async function getProducts() {
    const response = await apiClient.get('/product')
    return response.data
}

export async function getProduct(productId) {
    const response = await apiClient.get(`/product/${productId}`)
    return response.data
}
