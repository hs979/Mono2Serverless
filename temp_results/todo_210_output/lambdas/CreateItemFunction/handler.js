const AWS = require('aws-sdk');
const { v1: uuidv1 } = require('uuid');
const { docClient } = require('/opt/nodejs/dynamodb-utils');

/**
 * Lambda handler for POST /item
 * Creates a new todo item for the authenticated user
 * @param {Object} event - API Gateway event
 * @param {Object} context - Lambda context
 * @returns {Object} API Gateway response
 */
exports.lambda_handler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        // Get user_id from pre-validated Cognito claims
        const user_id = event.requestContext.authorizer.claims.sub; // UUID
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
        const todoId = uuidv1();
        const todoItem = {
            userId: user_id,
            todoId: todoId,
            item: item,
            completed: completed || false,
            creation_date: now,
            lastupdate_date: now
        };
        
        const params = {
            TableName: process.env.TODOS_TABLE,
            Item: todoItem
        };
        
        await docClient.put(params).promise();
        
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