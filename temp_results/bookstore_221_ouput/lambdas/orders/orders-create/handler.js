/**
 * Lambda handler for POST /orders
 * Create new order (checkout process)
 */

const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');
const { call_lambda } = require('/opt/nodejs/internalClient');

const dynamodb = new AWS.DynamoDB();
const docClient = new AWS.DynamoDB.DocumentClient({ service: dynamodb });

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const ORDERS_TABLE = process.env.ORDERS_TABLE;
        const CART_TABLE = process.env.CART_TABLE;
        if (!ORDERS_TABLE || !CART_TABLE) {
            throw new Error('Required environment variables not set');
        }
        
        // Get user_id from Cognito claims
        const user_id = event.requestContext.authorizer.claims.sub;
        
        const body = JSON.parse(event.body);
        const { books } = body;

        if (!books || !Array.isArray(books) || books.length === 0) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({ 
                    error: 'Missing or invalid books array' 
                })
            };
        }

        // Generate order ID
        const orderId = uuidv4();

        // 1. Create order
        const orderParams = {
            TableName: ORDERS_TABLE,
            Item: {
                customerId: user_id,
                orderId: orderId,
                orderDate: Date.now(),
                books: books
            }
        };

        await docClient.put(orderParams).promise();

        // 2. Remove checked out items from cart
        const deletePromises = books.map(book => {
            const deleteParams = {
                TableName: CART_TABLE,
                Key: {
                    customerId: user_id,
                    bookId: book.bookId
                }
            };
            return docClient.delete(deleteParams).promise();
        });

        await Promise.all(deletePromises);

        // 3. Call internal bestsellers-update Lambda asynchronously
        // Fire and forget - don't await
        call_lambda('/internal/bestsellers/update', 'POST', { books })
            .then(result => {
                if (result.statusCode >= 200 && result.statusCode < 300) {
                    console.log(`Bestseller updated: ${books.length} books`);
                } else {
                    console.warn(`Bestseller update failed: ${result.body}`);
                }
            })
            .catch(error => {
                // Bestseller update failure should not affect order creation
                console.error('Error updating bestsellers:', error);
            });

        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({ 
                message: 'Order created successfully',
                orderId: orderId
            })
        };
    } catch (error) {
        console.error('Error in POST /orders:', error);
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
