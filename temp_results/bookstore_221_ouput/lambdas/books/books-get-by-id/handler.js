/**
 * Lambda handler for GET /books/{id}
 * Get detailed info of a single book
 */

const AWS = require('aws-sdk');

const dynamodb = new AWS.DynamoDB();
const docClient = new AWS.DynamoDB.DocumentClient({ service: dynamodb });

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const BOOKS_TABLE = process.env.BOOKS_TABLE;
        if (!BOOKS_TABLE) {
            throw new Error('BOOKS_TABLE environment variable is not set');
        }
        
        const bookId = event.pathParameters ? event.pathParameters.id : null;
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
            TableName: BOOKS_TABLE,
            Key: {
                id: bookId
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
                body: JSON.stringify({ error: 'Book not found' })
            };
        }
    } catch (error) {
        console.error('Error in GET /books/{id}:', error);
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
