/**
 * Authentication Middleware
 * Supports JWT authentication and development mode
 */

const config = require('../config');
const { verifyAccessToken, extractTokenFromHeader } = require('../utils/jwt');

/**
 * JWT Authentication Middleware
 * Verifies Bearer token and extracts user info
 * 
 * Supports two modes:
 * 1. Production Mode (AUTH_DEV_MODE=false): Must provide valid JWT token
 * 2. Development Mode (AUTH_DEV_MODE=true): Allows skipping verification using x-customer-id header
 */
function authMiddleware(req, res, next) {
  // Development mode: Allow x-customer-id header
  if (config.auth.devMode) {
    const customerId = req.headers['x-customer-id'];
    if (customerId) {
      req.customerId = customerId;
      req.isDevMode = true;
      return next();
    }
  }

  // Get Authorization header
  const authHeader = req.headers.authorization;
  
  // Extract token
  const token = extractTokenFromHeader(authHeader);
  
  if (!token) {
    // If in development mode and no token provided, use default user ID
    if (config.auth.devMode) {
      req.customerId = 'default-customer-id';
      req.isDevMode = true;
      return next();
    }
    
    // Production mode must provide token
    return res.status(401).json({ 
      error: 'Authentication required. Please provide a valid Bearer token.' 
    });
  }

  // Verify token
  const payload = verifyAccessToken(token);
  
  if (!payload) {
    return res.status(401).json({ 
      error: 'Invalid or expired token' 
    });
  }

  // Add user info to request object
  req.customerId = payload.userId;
  req.userEmail = payload.email;
  req.isDevMode = false;

  next();
}

/**
 * Optional Authentication Middleware
 * Verifies token if provided, otherwise continues (for public interfaces)
 */
function optionalAuthMiddleware(req, res, next) {
  // Development mode
  if (config.auth.devMode) {
    const customerId = req.headers['x-customer-id'];
    if (customerId) {
      req.customerId = customerId;
      req.isDevMode = true;
    }
  }

  // Get Authorization header
  const authHeader = req.headers.authorization;
  const token = extractTokenFromHeader(authHeader);
  
  if (token) {
    // Verify token
    const payload = verifyAccessToken(token);
    
    if (payload) {
      req.customerId = payload.userId;
      req.userEmail = payload.email;
      req.isDevMode = false;
    }
  }

  // Continue regardless of token presence
  next();
}

module.exports = {
  authMiddleware,
  optionalAuthMiddleware
};
