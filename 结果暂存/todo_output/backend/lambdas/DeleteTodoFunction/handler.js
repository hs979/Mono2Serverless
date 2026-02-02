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
            }
        };
        
        await dynamodb.delete(params).promise();
        
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