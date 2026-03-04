/**
 * Internal Lambda handler for POST /internal/search-sync/bulk
 * Batch index books in Elasticsearch
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
 * Convert DynamoDB format to plain JSON format
 */
function convertDynamoDBFormat(data) {
    const result = {};
    
    for (const key in data) {
        const value = data[key];
        
        // If it's DynamoDB type marker format
        if (value && typeof value === 'object' && !Array.isArray(value)) {
            // Check for type markers
            if ('S' in value) {
                // String type
                result[key] = { S: value.S };
            } else if ('N' in value) {
                // Number type
                result[key] = { N: value.N };
            } else if ('BOOL' in value) {
                // Boolean type
                result[key] = { BOOL: value.BOOL };
            } else if ('L' in value) {
                // List type
                result[key] = { L: value.L };
            } else if ('M' in value) {
                // Map type
                result[key] = { M: value.M };
            } else {
                // Plain object, use directly
                result[key] = value;
            }
        } else {
            // Plain value, use directly
            result[key] = value;
        }
    }
    
    return result;
}

/**
 * Add or update book in search index
 */
async function indexBook(bookId, bookData) {
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
        // Convert DynamoDB data format to Elasticsearch format
        const document = convertDynamoDBFormat(bookData);
        
        // Use book ID as document ID, will create if not exists, update if exists
        await esClient.index({
            index: ES_INDEX,
            id: bookId,
            body: document
        });

        console.log(`Indexed book in Elasticsearch: bookId=${bookId}`);
        return true;
    } catch (error) {
        // Search index update failure should not affect main business logic
        console.error('Failed to index book in Elasticsearch:', error);
        return false;
    }
}

/**
 * Batch index books
 */
async function bulkIndexBooks(books) {
    if (!books || books.length === 0) {
        return { success: 0, failed: 0 };
    }

    let success = 0;
    let failed = 0;

    for (const book of books) {
        const result = await indexBook(book.id, book);
        if (result) {
            success++;
        } else {
            failed++;
        }
    }

    return { success, failed };
}

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const body = JSON.parse(event.body);
        const { books } = body;
        
        if (!books || !Array.isArray(books) || books.length === 0) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    error: 'Missing or invalid books array' 
                })
            };
        }

        const result = await bulkIndexBooks(books);
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(result)
        };
    } catch (error) {
        console.error('Error in internal search sync bulk:', error);
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
