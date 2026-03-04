/**
 * Lambda handler for GET /bestsellers
 * Returns top 20 bestseller book IDs
 */

const redis = require('redis');
const { promisify } = require('util');

let redisClient = null;
let zrevrangeAsync = null;

// Initialize Redis client
function initRedis() {
    const REDIS_ENABLED = process.env.REDIS_ENABLED === 'true' || process.env.REDIS_ENABLED === '1';
    const REDIS_HOST = process.env.REDIS_HOST || 'localhost';
    const REDIS_PORT = process.env.REDIS_PORT || 6379;
    const REDIS_PASSWORD = process.env.REDIS_PASSWORD;
    
    if (REDIS_ENABLED && !redisClient) {
        try {
            redisClient = redis.createClient({
                host: REDIS_HOST,
                port: REDIS_PORT,
                password: REDIS_PASSWORD,
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

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const REDIS_ENABLED = process.env.REDIS_ENABLED === 'true' || process.env.REDIS_ENABLED === '1';
        
        // If Redis is not enabled or not connected, return empty array
        if (!REDIS_ENABLED || !redisClient) {
            console.warn('Redis not available, returning empty array');
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify([])
            };
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
        // If Redis error, return empty array instead of error
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
