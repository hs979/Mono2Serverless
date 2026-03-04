const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');
const redis = require('redis');
const { promisify } = require('util');

const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * Simplified Redis client for Lambda
 * Lambda functions are stateless, so we create client on each invocation
 */
async function updateBestSellers(books) {
  const redisEndpoint = process.env.REDIS_ENDPOINT;
  
  if (!redisEndpoint) {
    console.log('REDIS_ENDPOINT not configured, skipping bestseller update');
    return { success: 0, failed: 0 };
  }

  try {
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

    const zincrbyAsync = promisify(redisClient.zincrby).bind(redisClient);
    
    let success = 0;
    let failed = 0;
    
    for (const book of books) {
      try {
        await zincrbyAsync('TopBooks:AllTime', book.quantity, JSON.stringify(book.bookId));
        console.log(`Updated bestseller: bookId=${book.bookId}, quantity=${book.quantity}`);
        success++;
      } catch (error) {
        console.error(`Failed to update bestseller for book ${book.bookId}:`, error);
        failed++;
      }
    }
    
    // Close Redis connection
    redisClient.quit();
    
    return { success, failed };
  } catch (error) {
    console.error('Redis connection error:', error);
    return { success: 0, failed: books.length };
  }
}

/**
 * POST /orders
 * Create new order (checkout process)
 */
exports.createOrder = async (event, context) => {
  try {
    // Get user_id from pre-validated Cognito claims
    const user_id = event.requestContext?.authorizer?.claims?.sub;
    
    if (!user_id) {
      return {
        statusCode: 401,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({ error: 'Unauthorized - user ID not found' })
      };
    }

    const body = JSON.parse(event.body || '{}');
    const { books } = body;

    if (!books || !Array.isArray(books) || books.length === 0) {
      return {
        statusCode: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({ error: 'Missing or invalid books array' })
      };
    }

    // Validate each book has required fields
    for (const book of books) {
      if (!book.bookId || !book.price || !book.quantity) {
        return {
          statusCode: 400,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
          },
          body: JSON.stringify({ error: 'Each book must have bookId, price, and quantity' })
        };
      }
    }

    const ordersTable = process.env.ORDERS_TABLE;
    const cartTable = process.env.CART_TABLE;
    const booksTable = process.env.BOOKS_TABLE;

    // Generate order ID
    const orderId = uuidv4();

    // 1. Create order
    const orderParams = {
      TableName: ordersTable,
      Item: {
        customerId: user_id,
        orderId: orderId,
        orderDate: Date.now(),
        books: books
      }
    };

    await dynamodb.put(orderParams).promise();

    // 2. Remove checked out items from cart
    const deletePromises = books.map(book => {
      const deleteParams = {
        TableName: cartTable,
        Key: {
          customerId: user_id,
          bookId: book.bookId
        }
      };
      return dynamodb.delete(deleteParams).promise();
    });

    await Promise.all(deletePromises);

    // 3. Sync update bestsellers (executed asynchronously, not blocking response)
    // Update logic runs in background
    updateBestSellers(books).then(result => {
      if (result.success > 0) {
        console.log(`Bestseller updated: ${result.success} books`);
      }
      if (result.failed > 0) {
        console.warn(`Bestseller update failed for ${result.failed} books`);
      }
    }).catch(error => {
      // Bestseller update failure should not affect order creation
      console.error('Error updating bestsellers:', error);
    });

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({ 
        message: 'Order created successfully',
        orderId: orderId
      })
    };
  } catch (error) {
    console.error('Error in POST /orders:', error);
    return {
      statusCode: 500,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({ error: 'Internal server error' })
    };
  }
};
