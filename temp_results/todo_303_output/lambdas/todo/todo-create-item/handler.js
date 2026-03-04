const AWS = require('aws-sdk');
const { v1: uuidv1 } = require('uuid');
const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * Lambda handler for POST /item
 * Creates a new todo item for the authenticated user.
 */
exports.handler = async (event) => {
    try {
        // Get user_id from Cognito claims
        const userId = event.requestContext.authorizer.claims.sub;
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
        const todoItem = {
            userId: userId,
            id: uuidv1(),
            item: item,
            completed: completed || false,
            creation_date: now,
            lastupdate_date: now
        };
        
        const params = {
            TableName: process.env.TODOS_TABLE,
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