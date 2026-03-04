/**
 * Lambda handler for PUT /cart
 * Update book quantity in cart
 */

const AWS = require('aws-sdk');

const dynamodb = new AWS.DynamoDB();
const docClient = new AWS.DynamoDB.DocumentClient({ service: dynamodb });

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const CART_TABLE = process.env.CART_TABLE;
        if (!CART_TABLE) {
            throw new Error('CART_TABLE environment variable is not set');
        }
        
        // Get user_id from Cognito claims
        const user_id = event.requestContext.authorizer.claims.sub;
        
        const body = JSON.parse(event.body);
        const { bookId, quantity } = body;

        if (!bookId || !quantity) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({ 
                    error: 'Missing required fields: bookId, quantity' 
                })
            };
        }

        const params = {
            TableName: CART_TABLE,
            Key: {
                customerId: user_id,
                bookId: bookId
            },
            UpdateExpression: 'SET quantity = :quantity',
            ExpressionAttributeValues: {
                ':quantity': quantity
            },
            ReturnValues: 'ALL_NEW'
        };

        await docClient.update(params).promise();
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({ message: 'Cart updated successfully' })
        };
    } catch (error) {
        console.error('Error in PUT /cart:', error);
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
