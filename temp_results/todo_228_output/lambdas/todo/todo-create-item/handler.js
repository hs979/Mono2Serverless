const AWS = require('aws-sdk');
const { v1: uuidv1 } = require('uuid');
const { invokeLambda } = require('/opt/nodejs/node_modules/internalClient');

const dynamodb = new AWS.DynamoDB.DocumentClient();
const TABLE_NAME = process.env.TODO_TABLE;

exports.lambdaHandler = async (event, context) => {
    try {
        // Get user_id from pre-validated Cognito claims
        const user_id = event.requestContext.authorizer.claims.sub; // UUID
        
        // Parse request body
        const body = JSON.parse(event.body || '{}');
        const { item, completed } = body;
        
        if (!item) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({
                    message: 'Invalid request: Todo item content cannot be empty'
                })
            };
        }
        
        const now = new Date().toISOString();
        const todoItem = {
            userId: user_id,
            id: uuidv1(),
            item: item,
            completed: completed || false,
            creation_date: now,
            lastupdate_date: now
        };
        
        const params = {
            TableName: TABLE_NAME,
            Item: todoItem
        };
        
        await dynamodb.put(params).promise();
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                message: 'Todo item created successfully',
                item: todoItem
            })
        };
        
    } catch (error) {
        console.error('Failed to create todo item:', error);
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
