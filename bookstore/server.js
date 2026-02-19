/**
 *Bookstore App - Main Server
 * This is a traditional Express.js application
 */

// Load environment variables
require('dotenv').config();

const express = require('express');
const path = require('path');
const cors = require('cors');
const bodyParser = require('body-parser');
const config = require('./config');

// Import route modules
const authRoutes = require('./routes/auth');
const booksRoutes = require('./routes/books');
const cartRoutes = require('./routes/cart');
const ordersRoutes = require('./routes/orders');
const bestSellersRoutes = require('./routes/bestsellers');
const recommendationsRoutes = require('./routes/recommendations');
const searchRoutes = require('./routes/search');

// Import authentication middleware
const { authMiddleware } = require('./middleware/auth');

const app = express();

// Middleware configuration
app.use(cors({
  origin: '*',
  credentials: true
}));
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));


// Authentication routes - No JWT verification required (register and login interfaces)
app.use('/api/auth', authRoutes);

// These routes require JWT authentication (or development mode)
app.use('/api/books', authMiddleware, booksRoutes);
app.use('/api/cart', authMiddleware, cartRoutes);
app.use('/api/orders', authMiddleware, ordersRoutes);
app.use('/api/bestsellers', authMiddleware, bestSellersRoutes);
app.use('/api/recommendations', authMiddleware, recommendationsRoutes);
app.use('/api/search', authMiddleware, searchRoutes);

// API root path - Returns API information
app.get('/api', (req, res) => {
  res.json({
    message: 'AWS Bookstore API',
    version: '1.0.0',
    authMode: config.auth.devMode ? 'development (JWT optional)' : 'production (JWT required)',
    endpoints: {
      auth: {
        register: 'POST /api/auth/register',
        login: 'POST /api/auth/login',
        refresh: 'POST /api/auth/refresh',
        me: 'GET /api/auth/me'
      },
      books: '/api/books',
      cart: '/api/cart',
      orders: '/api/orders',
      bestsellers: '/api/bestsellers',
      recommendations: '/api/recommendations',
      search: '/api/search'
    }
  });
});


// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal Server Error',
    stack: config.nodeEnv === 'development' ? err.stack : undefined
  });
});

// Start server
const PORT = config.port || 3000;
app.listen(PORT, () => {
  console.log(`========================================`);
  console.log(`🚀 AWS Bookstore App is running`);
  console.log(`========================================`);
  console.log(`📍 Access URL: http://localhost:${PORT}`);
  console.log(`🌍 Environment: ${config.nodeEnv}`);
  console.log(`🔐 Auth Mode: ${config.auth.devMode ? 'Development Mode (JWT Optional)' : 'Production Mode (JWT Required)'}`);
  console.log(`========================================`);
  console.log(`🔌 API Documentation: http://localhost:${PORT}/api`);
  console.log(`========================================`);
  console.log(`Auth Endpoints:`);
  console.log(`  POST   /api/auth/register      - User Register`);
  console.log(`  POST   /api/auth/login         - User Login`);
  console.log(`  POST   /api/auth/refresh       - Refresh Token`);
  console.log(`  GET    /api/auth/me            - Get Current User Info`);
  console.log(`========================================`);
  console.log(`API Endpoints:`);
  console.log(`  GET    /api/books              - List All Books`);
  console.log(`  GET    /api/books?category=X   - List Books by Category`);
  console.log(`  GET    /api/books/:id          - Get Single Book Info`);
  console.log(`  GET    /api/cart               - Get Cart`);
  console.log(`  POST   /api/cart               - Add to Cart`);
  console.log(`  PUT    /api/cart               - Update Cart`);
  console.log(`  DELETE /api/cart               - Remove from Cart`);
  console.log(`  GET    /api/cart/:bookId       - Get Specific Book in Cart`);
  console.log(`  GET    /api/orders             - Get Order List`);
  console.log(`  POST   /api/orders             - Create Order (Checkout)`);
  console.log(`  GET    /api/bestsellers        - Get Bestsellers List`);
  console.log(`  GET    /api/recommendations    - Get Recommended Books`);
  console.log(`  GET    /api/recommendations/:bookId - Get Recommendations by Book`);
  console.log(`  GET    /api/search?q=keyword   - Search Books`);
  console.log(`========================================`);
});

module.exports = app;
