const AWS = require('aws-sdk');

/**
 * Shared DynamoDB DocumentClient configuration for Lambda functions
 * Uses environment variables for configuration
 */

// Configure AWS SDK
AWS.config.update({
    region: process.env.AWS_REGION || 'us-east-1'
});

// Create DocumentClient with optimized settings for Lambda
const docClient = new AWS.DynamoDB.DocumentClient({
    region: process.env.AWS_REGION || 'us-east-1',
    httpOptions: {
        connectTimeout: 1000,
        timeout: 5000
    },
    maxRetries: 3
});

/**
 * Helper function to build query parameters for user-specific queries
 * @param {string} tableName - DynamoDB table name
 * @param {string} userId - Cognito Sub UUID
 * @param {Object} options - Additional query options
 * @returns {Object} DynamoDB query parameters
 */
function buildUserQueryParams(tableName, userId, options = {}) {
    const params = {
        TableName: tableName,
        KeyConditionExpression: '#userId = :userId',
        ExpressionAttributeNames: {
            '#userId': 'userId'
        },
        ExpressionAttributeValues: {
            ':userId': userId
        }
    };
    
    // Merge additional options
    if (options.filterExpression) {
        params.FilterExpression = options.filterExpression;
    }
    if (options.expressionAttributeNames) {
        params.ExpressionAttributeNames = {
            ...params.ExpressionAttributeNames,
            ...options.expressionAttributeNames
        };
    }
    if (options.expressionAttributeValues) {
        params.ExpressionAttributeValues = {
            ...params.ExpressionAttributeValues,
            ...options.expressionAttributeValues
        };
    }
    if (options.limit) {
        params.Limit = options.limit;
    }
    if (options.scanIndexForward !== undefined) {
        params.ScanIndexForward = options.scanIndexForward;
    }
    
    return params;
}

/**
 * Helper function to build key for user-specific items
 * @param {string} userId - Cognito Sub UUID
 * @param {string} itemId - Item ID (e.g., todoId)
 * @returns {Object} DynamoDB key object
 */
function buildUserItemKey(userId, itemId) {
    return {
        userId: userId,
        todoId: itemId
    };
}

/**
 * Helper function to handle DynamoDB errors
 * @param {Error} error - DynamoDB error
 * @returns {Object} Standardized error response
 */
function handleDynamoDBError(error) {
    console.error('DynamoDB Error:', error);
    
    if (error.code === 'ResourceNotFoundException') {
        return {
            statusCode: 404,
            message: 'Table not found. Please check if the table exists.'
        };
    } else if (error.code === 'ConditionalCheckFailedException') {
        return {
            statusCode: 409,
            message: 'Condition check failed. Item may have been modified.'
        };
    } else if (error.code === 'ProvisionedThroughputExceededException') {
        return {
            statusCode: 429,
            message: 'Request rate too high. Please try again later.'
        };
    } else {
        return {
            statusCode: 500,
            message: `Database error: ${error.message}`
        };
    }
}

module.exports = {
    docClient,
    buildUserQueryParams,
    buildUserItemKey,
    handleDynamoDBError
};