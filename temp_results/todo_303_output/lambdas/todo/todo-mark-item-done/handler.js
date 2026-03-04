const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * Lambda handler for POST /item/{id}/done
 * Marks a todo item as completed for the authenticated user.
 */
exports.handler = async (event) => {
    try {
        // Get user_id from Cognito claims
        const userId = event.requestContext.authorizer.claims.sub;
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
                userId: userId,
                id: id
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
        
        const result = await dynamodb.update(params).promise();
        
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