const AWS = require('aws-sdk');

const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * GET /cart/{bookId}
 * Get specific book info in cart
 */
exports.getCartItem = async (event, context) => {
  try {
    // Get user_id from pre-validated Cognito claims
    const user_id = event.requestContext?.authorizer?.claims?.sub;
    const bookId = event.pathParameters?.bookId;
    
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

    if (!bookId) {
      return {
        statusCode: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({ error: 'Book ID is required' })
      };
    }

    const cartTable = process.env.CART_TABLE;

    const params = {
      TableName: cartTable,
      Key: {
        customerId: user_id,
        bookId: bookId
      }
    };

    const data = await dynamodb.get(params).promise();
    
    if (data.Item) {
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify(data.Item)
      };
    } else {
      return {
        statusCode: 404,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({ error: 'Item not found in cart' })
      };
    }
  } catch (error) {
    console.error('Error in GET /cart/{bookId}:', error);
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
