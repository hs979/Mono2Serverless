const AWS = require('aws-sdk');
const { docClient } = require('/opt/nodejs/dynamodb-utils');

/**
 * Lambda handler for PUT /item/{id}
 * Updates an existing todo item for the authenticated user
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
        const body = JSON.parse(event.body);
        const { item, completed } = body;
        
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
        
        if (item === undefined || completed === undefined) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({
                    message: 'Invalid request: Missing required fields'
                })
            };
        }
        
        const params = {
            TableName: process.env.TODOS_TABLE,
            Key: {
                userId: user_id,
                todoId: id
            },
            UpdateExpression: 'set completed = :c, lastupdate_date = :lud, #i = :i',
            ExpressionAttributeNames: {
                '#i': 'item'
            },
            ExpressionAttributeValues: {
                ':c': completed,
                ':lud': new Date().toISOString(),
                ':i': item
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
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                message: error.message
            })
        };
    }
};