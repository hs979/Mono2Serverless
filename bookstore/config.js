/**
 * Application Configuration File
 * Manages all environment variables and configuration parameters
 */

// Load environment variables
require('dotenv').config();

const PORT = process.env.PORT || 3000;
const NODE_ENV = process.env.NODE_ENV || 'development';
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-in-production';
const JWT_REFRESH_SECRET = process.env.JWT_REFRESH_SECRET || 'your-refresh-secret-key-change-in-production';
const JWT_ACCESS_TOKEN_EXPIRY = process.env.JWT_ACCESS_TOKEN_EXPIRY || '1h';
const JWT_REFRESH_TOKEN_EXPIRY = process.env.JWT_REFRESH_TOKEN_EXPIRY || '7d';
const AUTH_DEV_MODE = process.env.AUTH_DEV_MODE === 'true';
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
const AWS_ACCESS_KEY_ID = process.env.AWS_ACCESS_KEY_ID;
const AWS_SECRET_ACCESS_KEY = process.env.AWS_SECRET_ACCESS_KEY;
const BOOKS_TABLE = process.env.BOOKS_TABLE || 'Bookstore-Books';
const CART_TABLE = process.env.CART_TABLE || 'Bookstore-Cart';
const ORDERS_TABLE = process.env.ORDERS_TABLE || 'Bookstore-Orders';
const USERS_TABLE = process.env.USERS_TABLE || 'Bookstore-Users';
const REDIS_HOST = process.env.REDIS_HOST || 'localhost';
const REDIS_PORT = process.env.REDIS_PORT || 6379;
const REDIS_PASSWORD = process.env.REDIS_PASSWORD;
const REDIS_ENABLED = process.env.REDIS_ENABLED !== 'false';
const ES_ENDPOINT = process.env.ES_ENDPOINT || 'localhost:9200';
const ES_INDEX = process.env.ES_INDEX || 'lambda-index';
const ES_TYPE = process.env.ES_TYPE || 'lambda-type';
const ES_ENABLED = process.env.ES_ENABLED !== 'false';
const NEPTUNE_ENDPOINT = process.env.NEPTUNE_ENDPOINT;
const NEPTUNE_PORT = process.env.NEPTUNE_PORT || 8182;
const NEPTUNE_ENABLED = process.env.NEPTUNE_ENABLED !== 'false';

const config = {
  // Server configuration
  port: PORT,
  nodeEnv: NODE_ENV,

  // JWT configuration
  jwt: {
    secret: JWT_SECRET,
    refreshSecret: JWT_REFRESH_SECRET,
    accessTokenExpiry: JWT_ACCESS_TOKEN_EXPIRY,
    refreshTokenExpiry: JWT_REFRESH_TOKEN_EXPIRY
  },

  // Auth mode configuration
  auth: {
    // Development mode: allows skipping JWT verification using x-customer-id header
    // Production mode: requires JWT authentication
    devMode: AUTH_DEV_MODE
  },

  // AWS configuration
  aws: {
    region: AWS_REGION,
    accessKeyId: AWS_ACCESS_KEY_ID,
    secretAccessKey: AWS_SECRET_ACCESS_KEY
  },

  // DynamoDB table names
  dynamodb: {
    booksTable: BOOKS_TABLE,
    cartTable: CART_TABLE,
    ordersTable: ORDERS_TABLE,
    usersTable: USERS_TABLE
  },

  // Redis configuration
  redis: {
    host: REDIS_HOST,
    port: REDIS_PORT,
    password: REDIS_PASSWORD,
    enabled: REDIS_ENABLED // Enabled by default
  },

  // Elasticsearch configuration
  elasticsearch: {
    endpoint: ES_ENDPOINT,
    index: ES_INDEX,
    type: ES_TYPE,
    enabled: ES_ENABLED // Enabled by default
  },

  // Neptune configuration
  neptune: {
    endpoint: NEPTUNE_ENDPOINT,
    port: NEPTUNE_PORT,
    enabled: NEPTUNE_ENABLED // Enabled by default
  }
};

module.exports = config;
