const AWS = require('aws-sdk');
const { docClient } = require('/opt/nodejs/dynamodb-utils');

/**
 * Lambda handler for POST /item/{id}/done
 * Marks a todo item as completed for the authenticated user
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
            },
            UpdateExpression: 'set #field = :value',
            ExpressionAttributeNames: {
                '#field': 'completed'
            },
            ExpressionAttributeValues: {
                ':value': true
            },
            ReturnValues: 'ALL_NEW'
        };
        
        const result = await docClient.update(params).promise();
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
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
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                message: error.message
            })
        };
    }
};