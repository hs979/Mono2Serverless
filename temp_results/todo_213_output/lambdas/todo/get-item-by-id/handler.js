const AWS = require('aws-sdk');

const docClient = new AWS.DynamoDB.DocumentClient();

/**
 * Lambda handler for GET /item/{id}
 * Retrieves a specific todo item by ID for the authenticated user.
 */
exports.handler = async (event, context) => {
  try {
    const claims = event.requestContext.authorizer.claims;
    const username = claims['cognito:username'] || claims.sub;
    const id = event.pathParameters.id;

    if (!id || !/^[\w-]+$/.test(id)) {
      return {
        statusCode: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
        body: JSON.stringify({
          message: 'Invalid request: Invalid todo item ID'
        })
      };
    }

    const params = {
      TableName: process.env.TODO_TABLE,
      Key: {
        "cognito-username": username,
        id: id
      }
    };

    const result = await docClient.get(params).promise();

    if (!result.Item) {
      return {
        statusCode: 404,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
        body: JSON.stringify({
          message: 'Todo item not found'
        })
      };
    }

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
      body: JSON.stringify(result)
    };

  } catch (error) {
    console.error('Failed to fetch todo item:', error);
    return {
      statusCode: 400,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
      body: JSON.stringify({
        message: error.message
      })
    };
  }
};
