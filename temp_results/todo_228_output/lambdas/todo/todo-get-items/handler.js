const AWS = require('aws-sdk');
const { invokeLambda } = require('/opt/nodejs/node_modules/internalClient');

const dynamodb = new AWS.DynamoDB.DocumentClient();
const TABLE_NAME = process.env.TODO_TABLE;

exports.lambdaHandler = async (event, context) => {
    try {
        // Get user_id from pre-validated Cognito claims
        const user_id = event.requestContext.authorizer.claims.sub; // UUID
        
        // Query parameters for pagination (optional)
        const queryParams = event.queryStringParameters || {};
        const limit = queryParams.limit ? parseInt(queryParams.limit) : 10;
        const exclusiveStartKey = queryParams.exclusiveStartKey ? JSON.parse(queryParams.exclusiveStartKey) : undefined;
        
        const params = {
            TableName: TABLE_NAME,
            KeyConditionExpression: "userId = :userId",
            ExpressionAttributeValues: {
                ":userId": user_id
            },
            Limit: limit,
            ExclusiveStartKey: exclusiveStartKey
        };
        
        const result = await dynamodb.query(params).promise();
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                Items: result.Items || [],
                Count: result.Count || 0,
                LastEvaluatedKey: result.LastEvaluatedKey
            })
        };
        
    } catch (error) {
        console.error('Failed to fetch todo list:', error);
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
