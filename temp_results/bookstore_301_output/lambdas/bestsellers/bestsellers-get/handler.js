const redis = require('redis');
const { promisify } = require('util');
const { success, error } = require('responseHelper');

let redisClient = null;
let zrevrangeAsync = null;

// Initialize Redis client
function initRedis() {
    const redisEnabled = process.env.REDIS_ENABLED === 'true';
    if (redisEnabled && !redisClient) {
        try {
            redisClient = redis.createClient({
                host: process.env.REDIS_HOST,
                port: process.env.REDIS_PORT,
                password: process.env.REDIS_PASSWORD || undefined,
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
        } catch (err) {
            console.error('Failed to initialize Redis:', err);
            redisClient = null;
        }
    }
}

// Initialize Redis on cold start
initRedis();

exports.lambdaHandler = async (event, context) => {
    try {
        const redisEnabled = process.env.REDIS_ENABLED === 'true';
        
        // If Redis is not enabled or not connected, return empty array
        if (!redisEnabled || !redisClient) {
            console.warn('Redis not available, returning empty array');
            return success([]);
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

        return success(bookIds);
    } catch (err) {
        console.error('Error in bestsellers-get:', err);
        // If Redis error, return empty array instead of error
        return success([]);
    }
};
