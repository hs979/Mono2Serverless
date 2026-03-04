const AWS = require('aws-sdk');

const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * GET /books
 * List all books or list books by category
 * Query params: category (optional)
 */
exports.getAllBooks = async (event, context) => {
  try {
    const category = event.queryStringParameters?.category;
    const booksTable = process.env.BOOKS_TABLE;

    if (category) {
      // Query by category
      const params = {
        TableName: booksTable,
        IndexName: 'category-index',
        KeyConditionExpression: 'category = :category',
        ExpressionAttributeValues: {
          ':category': category
        }
      };

      const data = await dynamodb.query(params).promise();
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify(data.Items)
      };
    } else {
      // List all books
      const params = {
        TableName: booksTable
      };

      const data = await dynamodb.scan(params).promise();
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify(data.Items)
      };
    }
  } catch (error) {
    console.error('Error in GET /books:', error);
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
