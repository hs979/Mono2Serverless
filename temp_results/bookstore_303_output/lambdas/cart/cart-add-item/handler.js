const AWS = require('aws-sdk');

const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * POST /cart
 * Add book to cart
 */
exports.addToCart = async (event, context) => {
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
    const { bookId, quantity, price } = body;

    if (!bookId || !quantity || !price) {
      return {
        statusCode: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({ error: 'Missing required fields: bookId, quantity, price' })
      };
    }

    const cartTable = process.env.CART_TABLE;

    const params = {
      TableName: cartTable,
      Item: {
        customerId: user_id,
        bookId: bookId,
        quantity: quantity,
        price: price
      }
    };

    await dynamodb.put(params).promise();
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({ message: 'Item added to cart successfully' })
    };
  } catch (error) {
    console.error('Error in POST /cart:', error);
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
