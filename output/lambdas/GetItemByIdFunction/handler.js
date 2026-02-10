const AWS = require('aws-sdk');
const { docClient } = require('/opt/nodejs/dynamodb-utils');

/**
 * Lambda handler for GET /item/{id}
 * Retrieves a specific todo item by ID for the authenticated user
 * @param {Object} event - API Gateway event
 * @param {Object} context - Lambda context
 * @returns {Object} API Gateway response
 */
exports.lambda_handler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        // Get user_id from pre-validated Cognito claims
        const user_id = event.requestContext.authorizer.claims.sub; // UUID
        const id = event.pathParameters.id;
        
        if (!id || !/^[\w-]+$/.test(id)) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({
                    message: 'Invalid request: Invalid todo item ID'
                })
            };
        }
        
        const params = {
            TableName: process.env.TODOS_TABLE,
            Key: {
                userId: user_id,
                todoId: id
            }
        };
        
        const result = await docClient.get(params).promise();
        
        if (!result.Item) {
            return {
                statusCode: 404,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
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
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify(result.Item)
        };
        
    } catch (error) {
        console.error('Failed to fetch todo item:', error);
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