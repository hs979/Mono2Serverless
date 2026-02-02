const AWS = require('aws-sdk');

// DynamoDB client configuration
const dynamodb = new AWS.DynamoDB.DocumentClient({
    region: process.env.AWS_REGION || 'us-east-1'
});

// Request/Response formatters
function formatResponse(statusCode, body, headers = {}) {
    const defaultHeaders = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    };
    
    return {
        statusCode,
        headers: { ...defaultHeaders, ...headers },
        body: JSON.stringify(body)
    };
}

function formatError(error, statusCode = 400) {
    console.error('Error:', error);
    return formatResponse(statusCode, {
        message: error.message || 'An error occurred'
    });
}

// Username extraction from Cognito
function getUsernameFromEvent(event) {
    try {
        // Extract username from Cognito authorizer claims
        if (event.requestContext.authorizer && event.requestContext.authorizer.claims) {
            return event.requestContext.authorizer.claims['cognito:username'] ||
                   event.requestContext.authorizer.claims.username;
        }
        
        // Alternative extraction from cognitoAuthenticationProvider
        if (event.requestContext.identity && event.requestContext.identity.cognitoAuthenticationProvider) {
            const authProvider = event.requestContext.identity.cognitoAuthenticationProvider;
            // Format: "cognito-idp.{region}.amazonaws.com/{userPoolId},{cognitoUserId}:{username}"
            const parts = authProvider.split(':');
            if (parts.length > 1) {
                return parts[parts.length - 1];
            }
        }
    } catch (error) {
        console.error('Failed to extract username from event:', error);
    }
    
    throw new Error('Unable to determine username from request');
}

// Validation utilities
function validateTodoId(id) {
    if (!id || !/^[\w-]+$/.test(id)) {
        throw new Error('Invalid todo item ID');
    }
    return true;
}

function validateTodoItem(item) {
    if (!item || item.trim() === '') {
        throw new Error('Todo item content cannot be empty');
    }
    return true;
}

// Export utilities
module.exports = {
    dynamodb,
    formatResponse,
    formatError,
    getUsernameFromEvent,
    validateTodoId,
    validateTodoItem
};