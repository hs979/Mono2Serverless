const redis = require('redis');
const { promisify } = require('util');

/**
 * GET /bestsellers
 * Get Bestsellers List (Top 20)
 */
exports.getBestsellers = async (event, context) => {
  try {
    const redisEndpoint = process.env.REDIS_ENDPOINT;
    
    if (!redisEndpoint) {
      console.warn('REDIS_ENDPOINT not configured, returning empty array');
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify([])
      };
    }

    // Parse Redis endpoint (format: host:port)
    const [host, port] = redisEndpoint.split(':');
    const redisClient = redis.createClient({
      host: host,
      port: parseInt(port) || 6379,
      retry_strategy: (options) => {
        // Quick retry for Lambda
        if (options.attempt > 3) {
          return undefined; // Stop retrying
        }
        return Math.min(options.attempt * 100, 1000);
      }
    });

    const zrevrangeAsync = promisify(redisClient.zrevrange).bind(redisClient);
    
    const key = 'TopBooks:AllTime';
    
    // Get top 20 from leaderboard
    // zrevrange returns members ordered by score from high to low
    const members = await zrevrangeAsync(key, 0, 19);
    
    // Close Redis connection
    redisClient.quit();
    
    // Clean up JSON formatted bookIds
    const bookIds = members.map(member => {
      try {
        return JSON.parse(member);
      } catch (e) {
        return member;
      }
    });

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify(bookIds)
    };
  } catch (error) {
    console.error('Error in GET /bestsellers:', error);
    // If Redis error, return empty array
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify([])
    };
  }
};
