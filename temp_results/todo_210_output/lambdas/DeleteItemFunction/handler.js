const AWS = require('aws-sdk');
const { docClient } = require('/opt/nodejs/dynamodb-utils');

/**
 * Lambda handler for DELETE /item/{id}
 * Deletes a todo item for the authenticated user
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
        
        await docClient.delete(params).promise();
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
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
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                message: error.message
            })
        };
    }
};