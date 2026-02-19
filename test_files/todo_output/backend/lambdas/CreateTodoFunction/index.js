const AWS = require('aws-sdk');
const { v1: uuidv1 } = require('uuid');
const dynamodb = new AWS.DynamoDB.DocumentClient();

const TODO_TABLE_NAME = process.env.TODO_TABLE_NAME;

function getUsernameFromEvent(event) {
    // Extract username from Cognito authorizer claims
    try {
        const authProvider = event.requestContext.identity.cognitoAuthenticationProvider;
        // cognitoAuthenticationProvider format: "cognito-idp.{region}.amazonaws.com/{userPoolId},{cognitoUserId}:{username}"
        const parts = authProvider.split(':');
        if (parts.length > 1) {
            return parts[parts.length - 1]; // username is the last part after colon
        }
    } catch (error) {
        console.error('Failed to extract username from event:', error);
    }
    
    // Fallback to using cognito:username from claims if available
    if (event.requestContext.authorizer && event.requestContext.authorizer.claims) {
        return event.requestContext.authorizer.claims['cognito:username'] ||
               event.requestContext.authorizer.claims.username;
    }
    
    throw new Error('Unable to determine username from request');
}

exports.handler = async (event) => {
    try {
        const username = getUsernameFromEvent(event);
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
            "cognito-username": username,
            "id": uuidv1(),
            "item": item,
            "completed": completed || false,
            "creation_date": now,
            "lastupdate_date": now
        };

        const params = {
            TableName: TODO_TABLE_NAME,
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