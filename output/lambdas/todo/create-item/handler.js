const AWS = require('aws-sdk');
const { v1: uuidv1 } = require('uuid');

const docClient = new AWS.DynamoDB.DocumentClient();

/**
 * Lambda handler for POST /item
 * Creates a new todo item for the authenticated user.
 */
exports.handler = async (event, context) => {
  try {
    const claims = event.requestContext.authorizer.claims;
    const username = claims['cognito:username'] || claims.sub;
    
    const body = JSON.parse(event.body);
    const { item, completed } = body;

    if (!item) {
      return {
        statusCode: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
        body: JSON.stringify({
          message: 'Invalid request: Todo item content cannot be empty'
        })
      };
    }
    
    const now = new Date().toISOString();
    const todoItem = {
      "cognito-username": username,
      id: uuidv1(),
      item: item,
      completed: completed || false,
      creation_date: now,
      lastupdate_date: now
    };

    const params = {
      TableName: process.env.TODO_TABLE,
      Item: todoItem
    };

    await docClient.put(params).promise();

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
      body: JSON.stringify({
        message: 'Todo item created successfully',
        item: todoItem
      })
    };

  } catch (error) {
    console.error('Failed to create todo item:', error);
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
