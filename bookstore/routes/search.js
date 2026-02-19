/**
 * Search Routes
 * Provides full-text search functionality using Elasticsearch
 */

const express = require('express');
const router = express.Router();
const AWS = require('aws-sdk');
const config = require('../config');

// Elasticsearch client (using AWS signed requests)
let esClient = null;

// Initialize Elasticsearch client
function initElasticsearch() {
  if (config.elasticsearch.enabled && config.elasticsearch.endpoint) {
    try {
      // Use @elastic/elasticsearch library
      const { Client } = require('@elastic/elasticsearch');
      const { createAWSConnection, awsGetCredentials } = require('@acuris/aws-es-connection');

      const awsCredentials = awsGetCredentials();
      const AWSConnection = createAWSConnection(AWS.config.credentials);

      esClient = new Client({
        node: `https://${config.elasticsearch.endpoint}`,
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

// Initialize Elasticsearch
initElasticsearch();

/**
 * GET /search?q=keyword
 * Search books (by name, author, category)
 * Query params: q - Search keyword
 */
router.get('/', async (req, res, next) => {
  try {
    const query = req.query.q;

    if (!query) {
      return res.status(400).json({ 
        error: 'Missing required query parameter: q' 
      });
    }

    // If Elasticsearch is not enabled or connected, use DynamoDB scan as fallback
    if (!config.elasticsearch.enabled || !esClient) {
      console.warn('Elasticsearch not available, using DynamoDB scan');
      return await searchWithDynamoDB(query, req, res, next);
    }

    // Build Elasticsearch query
    const searchQuery = {
      index: config.elasticsearch.index,
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
    res.json({
      total: result.body.hits.total.value || result.body.hits.total,
      hits: result.body.hits.hits
    });
  } catch (error) {
    console.error('Error in GET /search:', error);
    // If Elasticsearch error, fallback to DynamoDB search
    try {
      await searchWithDynamoDB(req.query.q, req, res, next);
    } catch (fallbackError) {
      next(fallbackError);
    }
  }
});

/**
 * Use DynamoDB scan as fallback for search
 * This is a simplified search implementation with lower performance
 */
async function searchWithDynamoDB(query, req, res, next) {
  const dynamoDb = new AWS.DynamoDB.DocumentClient({
    region: config.aws.region
  });

  const params = {
    TableName: config.dynamodb.booksTable
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

  res.json({
    total: results.length,
    hits: results.map(item => ({
      _source: item
    }))
  });
}

module.exports = router;
