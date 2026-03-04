/**
 * Lambda handler for GET /cart/{bookId}
 * Get specific book info in cart
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
        const bookId = event.pathParameters ? event.pathParameters.bookId : null;
        
        if (!bookId) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({ error: 'Book ID is required' })
            };
        }

        const params = {
            TableName: CART_TABLE,
            Key: {
                customerId: user_id,
                bookId: bookId
            }
        };

        const data = await docClient.get(params).promise();
        
        if (data.Item) {
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify(data.Item)
            };
        } else {
            return {
                statusCode: 404,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({ error: 'Item not found in cart' })
            };
        }
    } catch (error) {
        console.error('Error in GET /cart/{bookId}:', error);
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
