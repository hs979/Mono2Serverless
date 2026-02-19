/**
 * Bestsellers Routes
 * Handles bestseller list queries
 * Uses Redis to store and query bestseller data
 */

const express = require('express');
const router = express.Router();
const redis = require('redis');
const { promisify } = require('util');
const config = require('../config');

let redisClient = null;
let zrevrangeAsync = null;

// Initialize Redis client
function initRedis() {
  if (config.redis.enabled && !redisClient) {
    try {
      redisClient = redis.createClient({
        host: config.redis.host,
        port: config.redis.port,
        password: config.redis.password,
        retry_strategy: (options) => {
          if (options.error && options.error.code === 'ECONNREFUSED') {
            console.error('Redis connection refused');
            return new Error('Redis server refused connection');
          }
          if (options.total_retry_time > 1000 * 60 * 60) {
            return new Error('Redis retry time exhausted');
          }
          if (options.attempt > 10) {
            return undefined;
          }
          return Math.min(options.attempt * 100, 3000);
        }
      });

      redisClient.on('error', (err) => {
        console.error('Redis error:', err);
      });

      redisClient.on('connect', () => {
        console.log('Redis connected successfully');
      });

      // Convert Redis commands to Promises
      zrevrangeAsync = promisify(redisClient.zrevrange).bind(redisClient);
    } catch (error) {
      console.error('Failed to initialize Redis:', error);
      redisClient = null;
    }
  }
}

// Initialize Redis
initRedis();

/**
 * GET /bestsellers
 * Get Bestsellers List (Top 20)
 */
router.get('/', async (req, res, next) => {
  try {
    // If Redis is not enabled or not connected, return mock data
    if (!config.redis.enabled || !redisClient) {
      console.warn('Redis not available, returning mock data');
      return res.json([]);
    }

    const key = 'TopBooks:AllTime';
    
    // Get top 20 from leaderboard
    // zrevrange returns members ordered by score from high to low
    const members = await zrevrangeAsync(key, 0, 19);
    
    // Clean up JSON formatted bookIds
    const bookIds = members.map(member => {
      try {
        return JSON.parse(member);
      } catch (e) {
        return member;
      }
    });

    res.json(bookIds);
  } catch (error) {
    console.error('Error in GET /bestsellers:', error);
    // If Redis error, return empty array instead of error
    res.json([]);
  }
});

module.exports = router;
