const AWS = require('aws-sdk');

const docClient = new AWS.DynamoDB.DocumentClient();

/**
 * Lambda handler for POST /item/{id}/done
 * Marks a todo item as completed for the authenticated user.
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
      },
      UpdateExpression: "set #field = :value",
      ExpressionAttributeNames: {
        "#field": "completed"
      },
      ExpressionAttributeValues: {
        ":value": true
      },
      ReturnValues: "ALL_NEW"
    };

    const result = await docClient.update(params).promise();

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
      body: JSON.stringify({
        message: 'Todo item marked as completed',
        Attributes: result.Attributes
      })
    };

  } catch (error) {
    console.error('Failed to mark todo item as completed:', error);
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
