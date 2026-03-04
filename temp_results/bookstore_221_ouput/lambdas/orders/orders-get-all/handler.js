/**
 * Lambda handler for GET /orders
 * List all orders for current user
 */

const AWS = require('aws-sdk');

const dynamodb = new AWS.DynamoDB();
const docClient = new AWS.DynamoDB.DocumentClient({ service: dynamodb });

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const ORDERS_TABLE = process.env.ORDERS_TABLE;
        if (!ORDERS_TABLE) {
            throw new Error('ORDERS_TABLE environment variable is not set');
        }
        
        // Get user_id from Cognito claims
        const user_id = event.requestContext.authorizer.claims.sub;
        
        const params = {
            TableName: ORDERS_TABLE,
            KeyConditionExpression: 'customerId = :customerId',
            ExpressionAttributeValues: {
                ':customerId': user_id
            }
        };

        const data = await docClient.query(params).promise();
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify(data.Items)
        };
    } catch (error) {
        console.error('Error in GET /orders:', error);
        return {
            statusCode: 500,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({ error: 'Internal server error' })
        };
    }
};
