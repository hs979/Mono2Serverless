const AWS = require('aws-sdk');
const { Client } = require('@elastic/elasticsearch');
const { createAWSConnection, awsGetCredentials } = require('@acuris/aws-es-connection');

const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * Use DynamoDB scan as fallback for search
 * This is a simplified search implementation with lower performance
 */
async function searchWithDynamoDB(query, booksTable) {
  const params = {
    TableName: booksTable
  };

  const data = await dynamodb.scan(params).promise();
  
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

/**
 * GET /search?q=keyword
 * Search books (by name, author, category)
 */
exports.searchBooks = async (event, context) => {
  try {
    const query = event.queryStringParameters?.q;
    const elasticsearchEndpoint = process.env.ELASTICSEARCH_ENDPOINT;
    const booksTable = process.env.BOOKS_TABLE;

    if (!query) {
      return {
        statusCode: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({ error: 'Missing required query parameter: q' })
      };
    }

    // If Elasticsearch is not configured, use DynamoDB scan as fallback
    if (!elasticsearchEndpoint) {
      console.warn('ELASTICSEARCH_ENDPOINT not configured, using DynamoDB scan');
      const result = await searchWithDynamoDB(query, booksTable);
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify(result)
      };
    }

    try {
      // Initialize Elasticsearch client with AWS signed requests
      const awsCredentials = awsGetCredentials();
      const AWSConnection = createAWSConnection(AWS.config.credentials);

      const esClient = new Client({
        node: `https://${elasticsearchEndpoint}`,
        ...AWSConnection
      });

      // Build Elasticsearch query
      const searchQuery = {
        index: 'lambda-index', // Default index name from original config
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
    } catch (esError) {
      console.error('Elasticsearch error:', esError);
      // If Elasticsearch error, fallback to DynamoDB search
      const result = await searchWithDynamoDB(query, booksTable);
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify(result)
      };
    }
  } catch (error) {
    console.error('Error in GET /search:', error);
    return {
      statusCode: 500,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({ error: 'Internal server error' })
    };
  }
};
