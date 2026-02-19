const AWS = require('aws-sdk');
const { v1: uuidv1 } = require('uuid');

const docClient = new AWS.DynamoDB.DocumentClient();

/**
 * Lambda handler for GET /item
 * Retrieves all todo items for the authenticated user.
 * User identity is obtained from Cognito authorizer claims.
 */
exports.handler = async (event, context) => {
  try {
    // Get user identifier from Cognito claims
    // Cognito User Pool uses 'sub' (UUID) as unique identifier.
    // The original monolith used 'username' (string). We'll use 'cognito:username' claim if available,
    // otherwise fallback to 'sub' and map to a string.
    const claims = event.requestContext.authorizer.claims;
    // Use 'cognito:username' (preferred username) or 'sub' (UUID)
    const username = claims['cognito:username'] || claims.sub;
    
    const params = {
      TableName: process.env.TODO_TABLE,
      KeyConditionExpression: "#username = :username",
      ExpressionAttributeNames: {
        "#username": "cognito-username"
      },
      ExpressionAttributeValues: {
        ":username": username
      }
    };

    const result = await docClient.query(params).promise();

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*', // CORS - adjust as needed
      },
      body: JSON.stringify({
        Items: result.Items || [],
        Count: result.Count || 0
      })
    };

  } catch (error) {
    console.error('Failed to fetch todo list:', error);
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
