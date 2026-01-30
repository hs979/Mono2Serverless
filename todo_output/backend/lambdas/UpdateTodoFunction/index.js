const AWS = require('aws-sdk');
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
            TableName: TODO_TABLE_NAME,
            Key: {
                "cognito-username": username,
                "id": id
            },
            UpdateExpression: "set completed = :c, lastupdate_date = :lud, #i = :i",
            ExpressionAttributeNames: {
                "#i": "item"
            },
            ExpressionAttributeValues: {
                ":c": completed,
                ":lud": new Date().toISOString(),
                ":i": item
            },
            ReturnValues: "ALL_NEW"
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