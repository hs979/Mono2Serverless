/**
 * Authentication Routes
 * Handles user registration, login, token refresh, etc.
 */

const express = require('express');
const router = express.Router();
const { v4: uuidv4 } = require('uuid');
const { docClient, dynamoDb } = require('../utils/dynamodb');
const config = require('../config');
const { generateAccessToken, generateRefreshToken, verifyRefreshToken } = require('../utils/jwt');
const { hashPassword, verifyPassword } = require('../utils/password');
const { authMiddleware } = require('../middleware/auth');

/**
 * POST /auth/register
 * User Registration
 * Body: { email, password, name }
 */
router.post('/register', async (req, res, next) => {
  try {
    const { email, password, name } = req.body;

    // Validate required fields
    if (!email || !password) {
      return res.status(400).json({ 
        error: 'Email and password are required' 
      });
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return res.status(400).json({ 
        error: 'Invalid email format' 
      });
    }

    // Validate password strength (at least 6 characters)
    if (password.length < 6) {
      return res.status(400).json({ 
        error: 'Password must be at least 6 characters long' 
      });
    }

    // Check if user already exists
    const checkParams = {
      TableName: config.dynamodb.usersTable,
      IndexName: 'email-index',
      KeyConditionExpression: 'email = :email',
      ExpressionAttributeValues: {
        ':email': email
      }
    };

    const existingUser = await docClient.query(checkParams).promise();
    
    if (existingUser.Items && existingUser.Items.length > 0) {
      return res.status(409).json({ 
        error: 'User with this email already exists' 
      });
    }

    // Hash password
    const hashedPassword = await hashPassword(password);

    // Create new user
    const userId = uuidv4();
    const params = {
      TableName: config.dynamodb.usersTable,
      Item: {
        userId: userId,
        email: email,
        password: hashedPassword,
        name: name || email.split('@')[0],
        createdAt: Date.now(),
        updatedAt: Date.now()
      }
    };

    await docClient.put(params).promise();

    // Generate tokens
    const accessToken = generateAccessToken({ userId, email });
    const refreshToken = generateRefreshToken({ userId });

    res.status(201).json({
      message: 'User registered successfully',
      user: {
        userId,
        email,
        name: params.Item.name
      },
      accessToken,
      refreshToken
    });
  } catch (error) {
    console.error('Error in POST /auth/register:', error);
    next(error);
  }
});

/**
 * POST /auth/login
 * User Login
 * Body: { email, password }
 */
router.post('/login', async (req, res, next) => {
  try {
    const { email, password } = req.body;

    // Validate required fields
    if (!email || !password) {
      return res.status(400).json({ 
        error: 'Email and password are required' 
      });
    }

    // Find user
    const params = {
      TableName: config.dynamodb.usersTable,
      IndexName: 'email-index',
      KeyConditionExpression: 'email = :email',
      ExpressionAttributeValues: {
        ':email': email
      }
    };

    const result = await docClient.query(params).promise();

    if (!result.Items || result.Items.length === 0) {
      return res.status(401).json({ 
        error: 'Invalid email or password' 
      });
    }

    const user = result.Items[0];

    // Verify password
    const isPasswordValid = await verifyPassword(password, user.password);
    
    if (!isPasswordValid) {
      return res.status(401).json({ 
        error: 'Invalid email or password' 
      });
    }

    // Generate tokens
    const accessToken = generateAccessToken({ 
      userId: user.userId, 
      email: user.email 
    });
    const refreshToken = generateRefreshToken({ 
      userId: user.userId 
    });

    res.json({
      message: 'Login successful',
      user: {
        userId: user.userId,
        email: user.email,
        name: user.name
      },
      accessToken,
      refreshToken
    });
  } catch (error) {
    console.error('Error in POST /auth/login:', error);
    next(error);
  }
});

/**
 * POST /auth/refresh
 * Refresh Access Token
 * Body: { refreshToken }
 */
router.post('/refresh', async (req, res, next) => {
  try {
    const { refreshToken } = req.body;

    if (!refreshToken) {
      return res.status(400).json({ 
        error: 'Refresh token is required' 
      });
    }

    // Verify refresh token
    const payload = verifyRefreshToken(refreshToken);
    
    if (!payload) {
      return res.status(401).json({ 
        error: 'Invalid or expired refresh token' 
      });
    }

    // Find user
    const params = {
      TableName: config.dynamodb.usersTable,
      Key: {
        userId: payload.userId
      }
    };

    const result = await docClient.get(params).promise();

    if (!result.Item) {
      return res.status(401).json({ 
        error: 'User not found' 
      });
    }

    const user = result.Item;

    // Generate new access token
    const accessToken = generateAccessToken({ 
      userId: user.userId, 
      email: user.email 
    });

    res.json({
      accessToken
    });
  } catch (error) {
    console.error('Error in POST /auth/refresh:', error);
    next(error);
  }
});

/**
 * GET /auth/me
 * Get current logged in user info
 * Requires JWT Authentication
 */
router.get('/me', authMiddleware, async (req, res, next) => {
  try {
    // customerId is set in auth middleware (parsed from JWT userId)
    const userId = req.customerId;

    if (!userId || userId === 'default-customer-id') {
      return res.status(401).json({ 
        error: 'Authentication required' 
      });
    }

    const params = {
      TableName: config.dynamodb.usersTable,
      Key: {
        userId: userId
      }
    };

    const result = await docClient.get(params).promise();

    if (!result.Item) {
      return res.status(404).json({ 
        error: 'User not found' 
      });
    }

    const user = result.Item;

    // Do not return password
    delete user.password;

    res.json({
      user: user
    });
  } catch (error) {
    console.error('Error in GET /auth/me:', error);
    next(error);
  }
});

module.exports = router;
