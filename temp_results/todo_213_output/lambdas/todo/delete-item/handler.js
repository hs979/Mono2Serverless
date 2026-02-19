const AWS = require('aws-sdk');

const docClient = new AWS.DynamoDB.DocumentClient();

/**
 * Lambda handler for DELETE /item/{id}
 * Deletes a todo item for the authenticated user.
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

    await docClient.delete(params).promise();

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
      body: JSON.stringify({
        message: 'Todo item deleted successfully'
      })
    };

  } catch (error) {
    console.error('Failed to delete todo item:', error);
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
