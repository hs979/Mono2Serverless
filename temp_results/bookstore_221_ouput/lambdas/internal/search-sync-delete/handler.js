/**
 * Internal Lambda handler for POST /internal/search-sync/delete
 * Delete book from search index
 */

const AWS = require('aws-sdk');

let esClient = null;

/**
 * Initialize Elasticsearch Client
 */
function initElasticsearchClient() {
    const ES_ENABLED = process.env.ES_ENABLED === 'true' || process.env.ES_ENABLED === '1';
    const ES_ENDPOINT = process.env.ES_ENDPOINT;
    const ES_INDEX = process.env.ES_INDEX || 'lambda-index';
    
    if (ES_ENABLED && ES_ENDPOINT && !esClient) {
        try {
            const { Client } = require('@elastic/elasticsearch');
            const { createAWSConnection, awsGetCredentials } = require('@acuris/aws-es-connection');

            const awsCredentials = awsGetCredentials();
            const AWSConnection = createAWSConnection(AWS.config.credentials);

            esClient = new Client({
                node: `https://${ES_ENDPOINT}`,
                ...AWSConnection
            });

            console.log('Elasticsearch client initialized for search sync');
        } catch (error) {
            console.error('Failed to initialize Elasticsearch:', error);
            console.warn('Search sync will be disabled');
            esClient = null;
        }
    }
}

/**
 * Delete book from search index
 */
async function deleteBook(bookId) {
    const ES_ENABLED = process.env.ES_ENABLED === 'true' || process.env.ES_ENABLED === '1';
    const ES_INDEX = process.env.ES_INDEX || 'lambda-index';
    
    // If Elasticsearch is not enabled, return directly
    if (!ES_ENABLED) {
        console.log('Elasticsearch not enabled, skipping search sync');
        return false;
    }

    // Initialize Elasticsearch client (if not already initialized)
    if (!esClient) {
        initElasticsearchClient();
    }

    // If initialization failed, return
    if (!esClient) {
        console.warn('Elasticsearch client not available, skipping search sync');
        return false;
    }

    try {
        await esClient.delete({
            index: ES_INDEX,
            id: bookId
        });

        console.log(`Deleted book from Elasticsearch: bookId=${bookId}`);
        return true;
    } catch (error) {
        // If document does not exist, it's not considered an error
        if (error.meta && error.meta.statusCode === 404) {
            console.log(`Book not found in Elasticsearch (already deleted): bookId=${bookId}`);
            return true;
        }
        
        // Other errors
        console.error('Failed to delete book from Elasticsearch:', error);
        return false;
    }
}

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const body = JSON.parse(event.body);
        const { bookId } = body;
        
        if (!bookId) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    error: 'Missing required field: bookId' 
                })
            };
        }

        const result = await deleteBook(bookId);
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                success: result 
            })
        };
    } catch (error) {
        console.error('Error in internal search sync delete:', error);
        return {
            statusCode: 500,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                error: 'Internal server error' 
            })
        };
    }
};
