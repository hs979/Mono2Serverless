/**
 * Lambda handler for GET /search
 * Search books (by name, author, category)
 */

const AWS = require('aws-sdk');

let esClient = null;

// Initialize Elasticsearch client
function initElasticsearch() {
    const ES_ENABLED = process.env.ES_ENABLED === 'true' || process.env.ES_ENABLED === '1';
    const ES_ENDPOINT = process.env.ES_ENDPOINT;
    const ES_INDEX = process.env.ES_INDEX || 'lambda-index';
    
    if (ES_ENABLED && ES_ENDPOINT) {
        try {
            // Use @elastic/elasticsearch library
            const { Client } = require('@elastic/elasticsearch');
            const { createAWSConnection, awsGetCredentials } = require('@acuris/aws-es-connection');

            const awsCredentials = awsGetCredentials();
            const AWSConnection = createAWSConnection(AWS.config.credentials);

            esClient = new Client({
                node: `https://${ES_ENDPOINT}`,
                ...AWSConnection
            });

            console.log('Elasticsearch client initialized');
        } catch (error) {
            console.error('Failed to initialize Elasticsearch:', error);
            console.warn('Will use simplified search without Elasticsearch');
            esClient = null;
        }
    }
}

// Initialize Elasticsearch on cold start
if (!esClient) {
    initElasticsearch();
}

/**
 * Use DynamoDB scan as fallback for search
 */
async function searchWithDynamoDB(query) {
    const dynamoDb = new AWS.DynamoDB.DocumentClient();
    const BOOKS_TABLE = process.env.BOOKS_TABLE;
    
    const params = {
        TableName: BOOKS_TABLE
    };

    const data = await dynamoDb.scan(params).promise();
    
    // Simple string match search
    const lowerQuery = query.toLowerCase();
    const results = data.Items.filter(item => {
        return (
            (item.name && item.name.toLowerCase().includes(lowerQuery)) ||
            (item.author && item.author.toLowerCase().includes(lowerQuery)) ||
            (item.category && item.category.toLowerCase().includes(lowerQuery))
        );
    });

    return {
        total: results.length,
        hits: results.map(item => ({
            _source: item
        }))
    };
}

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const query = event.queryStringParameters ? event.queryStringParameters.q : null;

        if (!query) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({ 
                    error: 'Missing required query parameter: q' 
                })
            };
        }

        const ES_ENABLED = process.env.ES_ENABLED === 'true' || process.env.ES_ENABLED === '1';
        const ES_INDEX = process.env.ES_INDEX || 'lambda-index';
        
        // If Elasticsearch is not enabled or not connected, use DynamoDB scan as fallback
        if (!ES_ENABLED || !esClient) {
            console.warn('Elasticsearch not available, using DynamoDB scan');
            const result = await searchWithDynamoDB(query);
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify(result)
            };
        }

        // Build Elasticsearch query
        const searchQuery = {
            index: ES_INDEX,
            body: {
                size: 25,
                query: {
                    multi_match: {
                        query: query,
                        fields: ['name.S', 'author.S', 'category.S']
                    }
                }
            }
        };

        const result = await esClient.search(searchQuery);

        // Return search results
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                total: result.body.hits.total.value || result.body.hits.total,
                hits: result.body.hits.hits
            })
        };
    } catch (error) {
        console.error('Error in GET /search:', error);
        // If Elasticsearch error, fallback to DynamoDB search
        try {
            const query = event.queryStringParameters ? event.queryStringParameters.q : '';
            const result = await searchWithDynamoDB(query);
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify(result)
            };
        } catch (fallbackError) {
            console.error('Fallback search also failed:', fallbackError);
            return {
                statusCode: 500,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({ error: 'Internal server error' })
            };
        }
    }
};
