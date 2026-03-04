const { success, error, badRequest } = require('responseHelper');
const { scanItems } = require('dynamodbHelper');

let esClient = null;

// Initialize Elasticsearch client
function initElasticsearch() {
    const elasticsearchEnabled = process.env.ELASTICSEARCH_ENABLED === 'true';
    const elasticsearchEndpoint = process.env.ELASTICSEARCH_ENDPOINT;
    const elasticsearchIndex = process.env.ELASTICSEARCH_INDEX || 'lambda-index';
    
    if (elasticsearchEnabled && elasticsearchEndpoint) {
        try {
            // Use @elastic/elasticsearch library
            const { Client } = require('@elastic/elasticsearch');
            const { createAWSConnection, awsGetCredentials } = require('@acuris/aws-es-connection');
            const AWS = require('aws-sdk');

            const awsCredentials = awsGetCredentials();
            const AWSConnection = createAWSConnection(AWS.config.credentials);

            esClient = new Client({
                node: `https://${elasticsearchEndpoint}`,
                ...AWSConnection
            });

            console.log('Elasticsearch client initialized');
        } catch (err) {
            console.error('Failed to initialize Elasticsearch:', err);
            console.warn('Will use simplified search without Elasticsearch');
            esClient = null;
        }
    }
}

// Initialize on cold start
if (!esClient) {
    initElasticsearch();
}

/**
 * Use DynamoDB scan as fallback for search
 * This is a simplified search implementation with lower performance
 */
async function searchWithDynamoDB(query) {
    const tableName = process.env.BOOKS_TABLE;
    if (!tableName) {
        throw new Error('BOOKS_TABLE environment variable not set');
    }

    const items = await scanItems(tableName);
    
    // Simple string match search
    const lowerQuery = query.toLowerCase();
    const results = items.filter(item => {
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
    try {
        const query = event.queryStringParameters?.q;

        if (!query) {
            return badRequest('Missing required query parameter: q');
        }

        const elasticsearchEnabled = process.env.ELASTICSEARCH_ENABLED === 'true';
        
        // If Elasticsearch is not enabled or not connected, use DynamoDB scan as fallback
        if (!elasticsearchEnabled || !esClient) {
            console.warn('Elasticsearch not available, using DynamoDB scan');
            const result = await searchWithDynamoDB(query);
            return success(result);
        }

        const index = process.env.ELASTICSEARCH_INDEX || 'lambda-index';
        // Build Elasticsearch query
        const searchQuery = {
            index: index,
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
        return success({
            total: result.body.hits.total.value || result.body.hits.total,
            hits: result.body.hits.hits
        });
    } catch (err) {
        console.error('Error in search-get:', err);
        // If Elasticsearch error, fallback to DynamoDB search
        try {
            const query = event.queryStringParameters?.q;
            if (query) {
                const result = await searchWithDynamoDB(query);
                return success(result);
            } else {
                return badRequest('Missing required query parameter: q');
            }
        } catch (fallbackErr) {
            console.error('Fallback search also failed:', fallbackErr);
            return error(fallbackErr.message);
        }
    }
};
