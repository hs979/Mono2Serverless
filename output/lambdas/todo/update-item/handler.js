const AWS = require('aws-sdk');

const docClient = new AWS.DynamoDB.DocumentClient();

/**
 * Lambda handler for PUT /item/{id}
 * Updates an existing todo item for the authenticated user.
 */
exports.handler = async (event, context) => {
  try {
    const claims = event.requestContext.authorizer.claims;
    const username = claims['cognito:username'] || claims.sub;
    const id = event.pathParameters.id;
    const body = JSON.parse(event.body);
    const { item, completed } = body;

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

    if (item === undefined || completed === undefined) {
      return {
        statusCode: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
        body: JSON.stringify({
          message: 'Invalid request: Missing required fields'
        })
      };
    }
    
    const params = {
      TableName: process.env.TODO_TABLE,
      Key: {
        "cognito-username": username,
        id: id
      },
      UpdateExpression: "set completed = :c, lastupdate_date = :lud, #i = :i",
      ExpressionAttributeNames: {
        "#i": "item"
      },
      ExpressionAttributeValues: {
        ":c": completed,
        ":lud": new Date().toISOString(),
        ":i": item
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
        message: 'Todo item updated successfully',
        Attributes: result.Attributes
      })
    };

  } catch (error) {
    console.error('Failed to update todo item:', error);
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
