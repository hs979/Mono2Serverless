const AWS = require('aws-sdk');

const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * GET /books/{id}
 * Get detailed info of a single book
 */
exports.getBookById = async (event, context) => {
  try {
    const bookId = event.pathParameters?.id;
    const booksTable = process.env.BOOKS_TABLE;

    if (!bookId) {
      return {
        statusCode: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({ error: 'Book ID is required' })
      };
    }

    const params = {
      TableName: booksTable,
      Key: {
        id: bookId
      }
    };

    const data = await dynamodb.get(params).promise();
    
    if (data.Item) {
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify(data.Item)
      };
    } else {
      return {
        statusCode: 404,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({ error: 'Book not found' })
      };
    }
  } catch (error) {
    console.error('Error in GET /books/{id}:', error);
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
