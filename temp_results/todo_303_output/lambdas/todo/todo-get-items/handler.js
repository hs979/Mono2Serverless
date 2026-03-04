const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * Lambda handler for GET /item
 * Retrieves all todo items for the authenticated user.
 */
exports.handler = async (event) => {
    try {
        // Get user_id from Cognito claims
        const userId = event.requestContext.authorizer.claims.sub;
        
        const params = {
            TableName: process.env.TODOS_TABLE,
            KeyConditionExpression: '#userId = :userId',
            ExpressionAttributeNames: {
                '#userId': 'userId'
            },
            ExpressionAttributeValues: {
                ':userId': userId
            }
        };
        
        const result = await dynamodb.query(params).promise();
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
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
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                message: error.message
            })
        };
    }
};