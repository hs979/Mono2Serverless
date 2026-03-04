const AWS = require('aws-sdk');
const { invokeLambda } = require('/opt/nodejs/node_modules/internalClient');

const dynamodb = new AWS.DynamoDB.DocumentClient();
const TABLE_NAME = process.env.TODO_TABLE;

exports.lambdaHandler = async (event, context) => {
    try {
        // Get user_id from pre-validated Cognito claims
        const user_id = event.requestContext.authorizer.claims.sub; // UUID
        
        // Extract id from path parameters
        const { id } = event.pathParameters || {};
        
        // Parse request body
        const body = JSON.parse(event.body || '{}');
        const { item, completed } = body;
        
        if (!id || !/^[\w-]+$/.test(id)) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({
                    message: 'Invalid request: Invalid todo item ID'
                })
            };
        }
        
        if (item === undefined || completed === undefined) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({
                    message: 'Invalid request: Missing required fields'
                })
            };
        }
        
        const params = {
            TableName: TABLE_NAME,
            Key: {
                userId: user_id,
                id: id
            },
            UpdateExpression: "set completed = :c, lastupdate_date = :lud, #i = :i",
            ExpressionAttributeNames: {
                "#i": "item"
            },
            ExpressionAttributeValues: {
                ":c": completed,
                ":lud": new Date().toISOString(),
                ":i": item
            },
            ReturnValues: "ALL_NEW"
        };
        
        const result = await dynamodb.update(params).promise();
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                message: 'Todo item updated successfully',
                Attributes: result.Attributes
            })
        };
        
    } catch (error) {
        console.error('Failed to update todo item:', error);
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
