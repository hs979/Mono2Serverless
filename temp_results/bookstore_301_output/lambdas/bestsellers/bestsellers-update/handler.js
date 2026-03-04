const redis = require('redis');
const { promisify } = require('util');
const { success, error } = require('responseHelper');

let redisClient = null;
let zincrbyAsync = null;

// Initialize Redis client
function initRedisClient() {
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
                console.log('Redis connected for bestsellers updates');
            });

            // Convert Redis commands to Promises
            zincrbyAsync = promisify(redisClient.zincrby).bind(redisClient);
        } catch (err) {
            console.error('Failed to initialize Redis:', err);
            redisClient = null;
        }
    }
}

// Initialize on cold start
if (!redisClient) {
    initRedisClient();
}

/**
 * Update Bestseller List
 * @param {string} bookId - Book ID
 * @param {number} quantity - Quantity sold
 * @returns {Promise<boolean>} Whether update was successful
 */
async function updateBestSeller(bookId, quantity) {
    // If Redis is not enabled, return directly
    const redisEnabled = process.env.REDIS_ENABLED === 'true';
    if (!redisEnabled) {
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
        // ZINCRBY key increment member
        // If member does not exist, it is created with score equal to increment
        await zincrbyAsync(key, quantity, JSON.stringify(bookId));
        
        console.log(`Updated bestseller: bookId=${bookId}, quantity=${quantity}`);
        return true;
    } catch (err) {
        // Bestseller update failure should not affect main business logic
        console.error('Failed to update bestseller:', err);
        return false;
    }
}

/**
 * Batch Update Bestsellers
 * @param {Array} books - Array of books, each element containing {bookId, quantity}
 * @returns {Promise<Object>} Update result statistics
 */
async function updateBestSellers(books) {
    if (!books || books.length === 0) {
        return { success: 0, failed: 0 };
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

    return { success, failed };
}

exports.lambdaHandler = async (event, context) => {
    try {
        // The event payload is passed from invokeLambda
        // Expecting an array of books: [{bookId, quantity}, ...]
        const books = event;
        
        if (!Array.isArray(books)) {
            return error('Invalid payload: expected array of books');
        }

        const result = await updateBestSellers(books);
        
        return success({
            message: 'Bestsellers update processed',
            ...result
        });
    } catch (err) {
        console.error('Error in bestsellers-update:', err);
        return error(err.message);
    }
};
