/**
 * Internal Lambda handler for POST /internal/bestsellers/update
 * Update bestseller rankings in Redis
 */

const redis = require('redis');
const { promisify } = require('util');

let redisClient = null;
let zincrbyAsync = null;

/**
 * Initialize Redis Client
 */
function initRedisClient() {
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
                console.log('Redis connected for bestsellers updates');
            });

            // Convert Redis commands to Promises
            zincrbyAsync = promisify(redisClient.zincrby).bind(redisClient);
        } catch (error) {
            console.error('Failed to initialize Redis:', error);
            redisClient = null;
        }
    }
}

/**
 * Update Bestseller List
 */
async function updateBestSeller(bookId, quantity) {
    const REDIS_ENABLED = process.env.REDIS_ENABLED === 'true' || process.env.REDIS_ENABLED === '1';
    
    // If Redis is not enabled, return directly
    if (!REDIS_ENABLED) {
        console.log('Redis not enabled, skipping bestseller update');
        return false;
    }

    // Initialize Redis client (if not already initialized)
    if (!redisClient) {
        initRedisClient();
    }

    // If initialization failed, return
    if (!redisClient) {
        console.warn('Redis client not available, skipping bestseller update');
        return false;
    }

    try {
        const key = 'TopBooks:AllTime';
        
        // Increase book sales score
        await zincrbyAsync(key, quantity, JSON.stringify(bookId));
        
        console.log(`Updated bestseller: bookId=${bookId}, quantity=${quantity}`);
        return true;
    } catch (error) {
        // Bestseller update failure should not affect main business logic
        console.error('Failed to update bestseller:', error);
        return false;
    }
}

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const body = JSON.parse(event.body);
        const { books } = body;
        
        if (!books || !Array.isArray(books) || books.length === 0) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    error: 'Missing or invalid books array' 
                })
            };
        }

        let success = 0;
        let failed = 0;

        for (const book of books) {
            const result = await updateBestSeller(book.bookId, book.quantity);
            if (result) {
                success++;
            } else {
                failed++;
            }
        }

        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                success, 
                failed 
            })
        };
    } catch (error) {
        console.error('Error in internal bestsellers update:', error);
        return {
            statusCode: 500,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                error: 'Internal server error' 
            })
        };
    }
};
