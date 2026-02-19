/**
 * JWT Utility Functions
 * Used for generating and verifying JSON Web Tokens
 */

const jwt = require('jsonwebtoken');
const config = require('../config');

/**
 * Generate Access Token
 * @param {Object} payload - Data to encode in token
 * @param {string} payload.userId - User ID
 * @param {string} payload.email - User email
 * @returns {string} JWT token
 */
function generateAccessToken(payload) {
  return jwt.sign(
    payload,
    config.jwt.secret,
    { 
      expiresIn: config.jwt.accessTokenExpiry,
      issuer: 'bookstore-api'
    }
  );
}

/**
 * Generate Refresh Token
 * @param {Object} payload - Data to encode in token
 * @param {string} payload.userId - User ID
 * @returns {string} JWT refresh token
 */
function generateRefreshToken(payload) {
  return jwt.sign(
    payload,
    config.jwt.refreshSecret,
    { 
      expiresIn: config.jwt.refreshTokenExpiry,
      issuer: 'bookstore-api'
    }
  );
}

/**
 * Verify Access Token
 * @param {string} token - JWT token
 * @returns {Object|null} Decoded payload, or null if failed
 */
function verifyAccessToken(token) {
  try {
    return jwt.verify(token, config.jwt.secret, {
      issuer: 'bookstore-api'
    });
  } catch (error) {
    console.error('Access token verification failed:', error.message);
    return null;
  }
}

/**
 * Verify Refresh Token
 * @param {string} token - JWT refresh token
 * @returns {Object|null} Decoded payload, or null if failed
 */
function verifyRefreshToken(token) {
  try {
    return jwt.verify(token, config.jwt.refreshSecret, {
      issuer: 'bookstore-api'
    });
  } catch (error) {
    console.error('Refresh token verification failed:', error.message);
    return null;
  }
}

/**
 * Extract Bearer token from request header
 * @param {string} authHeader - Authorization request header
 * @returns {string|null} Token string, or null if failed
 */
function extractTokenFromHeader(authHeader) {
  if (!authHeader) {
    return null;
  }

  const parts = authHeader.split(' ');
  if (parts.length !== 2 || parts[0] !== 'Bearer') {
    return null;
  }

  return parts[1];
}

module.exports = {
  generateAccessToken,
  generateRefreshToken,
  verifyAccessToken,
  verifyRefreshToken,
  extractTokenFromHeader
};
