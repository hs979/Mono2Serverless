const AWS = require('aws-sdk');

const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * GET /orders
 * List all orders for current user
 */
exports.getOrders = async (event, context) => {
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

    const ordersTable = process.env.ORDERS_TABLE;

    const params = {
      TableName: ordersTable,
      KeyConditionExpression: 'customerId = :customerId',
      ExpressionAttributeValues: {
        ':customerId': user_id
      }
    };

    const data = await dynamodb.query(params).promise();
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify(data.Items)
    };
  } catch (error) {
    console.error('Error in GET /orders:', error);
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
