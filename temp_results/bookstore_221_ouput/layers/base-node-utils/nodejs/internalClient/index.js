/**
 * Internal Client for Lambda-to-Lambda HTTP calls
 * Provides call_lambda function to call other Lambdas via API Gateway
 */

const AWS = require('aws-sdk');

/**
 * Call another Lambda function via API Gateway
 * @param {string} internalPath - The internal path (e.g., '/internal/bestsellers/update')
 * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
 * @param {Object} payload - Request body (will be JSON stringified)
 * @param {Object} headers - Additional headers
 * @returns {Promise<Object>} Response object with statusCode and body
 */
async function call_lambda(internalPath, method, payload, headers = {}) {
    const baseUrl = process.env.INTERNAL_API_BASE_URL;
    if (!baseUrl) {
        throw new Error('INTERNAL_API_BASE_URL environment variable is not set');
    }

    const url = `${baseUrl}${internalPath}`;
    
    const defaultHeaders = {
        'Content-Type': 'application/json',
        ...headers
    };

    try {
        const response = await fetch(url, {
            method: method,
            headers: defaultHeaders,
            body: payload ? JSON.stringify(payload) : undefined
        });

        const responseBody = await response.text();
        
        return {
            statusCode: response.status,
            body: responseBody
        };
    } catch (error) {
        console.error(`Error calling internal Lambda: ${url}`, error);
        throw new Error(`Internal Lambda call failed: ${error.message}`);
    }
}

module.exports = {
    call_lambda
};
