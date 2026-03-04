/**
 * Lambda handler for GET /books
 * List all books or list books by category
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
        
        const category = event.queryStringParameters ? event.queryStringParameters.category : null;

        if (category) {
            // Query by category
            const params = {
                TableName: BOOKS_TABLE,
                IndexName: 'category-index',
                KeyConditionExpression: 'category = :category',
                ExpressionAttributeValues: {
                    ':category': category
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
        } else {
            // List all books
            const params = {
                TableName: BOOKS_TABLE
            };

            const data = await docClient.scan(params).promise();
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify(data.Items)
            };
        }
    } catch (error) {
        console.error('Error in GET /books:', error);
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
