const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');
const dynamodb = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
    try {
        // Extract user ID from Cognito JWT token
        const userId = event.requestContext.authorizer.claims.sub;
        // Parse request body
        const body = JSON.parse(event.body);
        const { item, completed } = body;
        
        if (!item) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({
                    message: 'Invalid request: Todo item content cannot be empty'
                })
            };
        }
        
        const now = new Date().toISOString();
        const todoId = uuidv4();
        const todoItem = {
            userId: userId,
            todoId: todoId,
            item: item,
            completed: completed || false,
            creation_date: now,
            lastupdate_date: now
        };
        
        const params = {
            TableName: process.env.TODO_TABLE_NAME,
            Item: todoItem
        };
        
        await dynamodb.put(params).promise();
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                message: 'Todo item created successfully',
                item: todoItem
            })
        };
        
    } catch (error) {
        console.error('Failed to create todo item:', error);
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