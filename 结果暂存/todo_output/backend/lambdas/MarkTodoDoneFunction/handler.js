const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
    try {
        // Extract user ID from Cognito JWT token
        const userId = event.requestContext.authorizer.claims.sub;
        // Extract todoId from path parameters
        const todoId = event.pathParameters.id;
        
        if (!todoId || !/^[\w-]+$/.test(todoId)) {
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
            TableName: process.env.TODO_TABLE_NAME,
            Key: {
                userId: userId,
                todoId: todoId
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