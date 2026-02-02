const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
    try {
        // Extract user ID from Cognito JWT token
        const userId = event.requestContext.authorizer.claims.sub;
        // Extract todoId from path parameters
        const todoId = event.pathParameters.id;
        // Parse request body
        const body = JSON.parse(event.body);
        const { item, completed } = body;
        
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
            TableName: process.env.TODO_TABLE_NAME,
            Key: {
                userId: userId,
                todoId: todoId
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
        
        const result = await dynamodb.update(params).promise();
        
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