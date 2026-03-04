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
        
        const params = {
            TableName: TABLE_NAME,
            Key: {
                userId: user_id,
                id: id
            },
            UpdateExpression: "set #field = :value",
            ExpressionAttributeNames: {
                "#field": "completed"
            },
            ExpressionAttributeValues: {
                ":value": true
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
                message: 'Todo item marked as completed',
                Attributes: result.Attributes
            })
        };
        
    } catch (error) {
        console.error('Failed to mark todo item as completed:', error);
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
