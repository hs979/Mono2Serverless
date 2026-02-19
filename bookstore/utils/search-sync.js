/**
 * Search Cluster Sync Utility Functions
 * Used for syncing book data to Elasticsearch
 */

const AWS = require('aws-sdk');
const config = require('../config');

let esClient = null;

/**
 * Initialize Elasticsearch Client
 */
function initElasticsearchClient() {
  if (config.elasticsearch.enabled && config.elasticsearch.endpoint && !esClient) {
    try {
      const { Client } = require('@elastic/elasticsearch');
      const { createAWSConnection, awsGetCredentials } = require('@acuris/aws-es-connection');

      const awsCredentials = awsGetCredentials();
      const AWSConnection = createAWSConnection(AWS.config.credentials);

      esClient = new Client({
        node: `https://${config.elasticsearch.endpoint}`,
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
 * Add or update book in search index
 * @param {string} bookId - Book ID
 * @param {Object} bookData - Book data
 * @returns {Promise<boolean>} Whether sync was successful
 */
async function indexBook(bookId, bookData) {
  // If Elasticsearch is not enabled, return directly
  if (!config.elasticsearch.enabled) {
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
    const index = config.elasticsearch.index || 'lambda-index';
    
    // Convert DynamoDB data format to Elasticsearch format
    // DynamoDB storage format might be like {S: "value"} type markers
    const document = convertDynamoDBFormat(bookData);
    
    // Use book ID as document ID, will create if not exists, update if exists
    await esClient.index({
      index: index,
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
 * Delete book from search index
 * @param {string} bookId - Book ID
 * @returns {Promise<boolean>} Whether deletion was successful
 */
async function deleteBook(bookId) {
  // If Elasticsearch is not enabled, return directly
  if (!config.elasticsearch.enabled) {
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
    const index = config.elasticsearch.index || 'lambda-index';
    
    await esClient.delete({
      index: index,
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

/**
 * Batch index books
 * @param {Array} books - Array of books, each element containing {id, ...bookData}
 * @returns {Promise<Object>} Indexing result statistics
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

/**
 * Convert DynamoDB format to plain JSON format
 * DynamoDB might use type markers like {S: "value", N: "123"}
 * Needs to be converted to plain format {field: "value", number: 123}
 * @param {Object} data - DynamoDB format data
 * @returns {Object} Plain JSON format data
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
 * Close Elasticsearch Client (used when app shuts down)
 */
function closeElasticsearchClient() {
  if (esClient) {
    esClient.close();
    esClient = null;
  }
}

module.exports = {
  indexBook,
  deleteBook,
  bulkIndexBooks,
  closeElasticsearchClient
};
