const AWS = require('aws-sdk');
const { docClient } = require('/opt/nodejs/dynamodb-utils');

/**
 * Lambda handler for GET /item
 * Retrieves all todo items for the authenticated user
 * @param {Object} event - API Gateway event
 * @param {Object} context - Lambda context
 * @returns {Object} API Gateway response
 */
exports.lambda_handler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        // Get user_id from pre-validated Cognito claims
        const user_id = event.requestContext.authorizer.claims.sub; // UUID
        
        const params = {
            TableName: process.env.TODOS_TABLE,
            KeyConditionExpression: '#userId = :userId',
            ExpressionAttributeNames: {
                '#userId': 'userId'
            },
            ExpressionAttributeValues: {
                ':userId': user_id
            }
        };
        
        const result = await docClient.query(params).promise();
        
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