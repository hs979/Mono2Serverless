/**
 * Books Related Routes
 * Handles book query operations
 */

const express = require('express');
const router = express.Router();
const { dynamodb, docClient } = require('../utils/dynamodb');
const { dynamodb: dynamodbConfig } = require('../config');
const authMiddleware = require('../middleware/auth');

const booksTable = dynamodbConfig.booksTable;

/**
 * GET /books
 * List all books or list books by category
 * Query params: category (optional)
 */
router.get('/', async (req, res, next) => {
  try {
    const category = req.query.category;

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

      const data = await docClient.query(params).promise();
      res.json(data.Items);
    } else {
      // List all books
      const params = {
        TableName: booksTable
      };

      const data = await docClient.scan(params).promise();
      res.json(data.Items);
    }
  } catch (error) {
    console.error('Error in GET /books:', error);
    next(error);
  }
});

/**
 * GET /books/:id
 * Get detailed info of a single book
 * Path params: id - Book ID
 */
router.get('/:id', async (req, res, next) => {
  try {
    const params = {
      TableName: booksTable,
      Key: {
        id: req.params.id
      }
    };

    const data = await docClient.get(params).promise();
    
    if (data.Item) {
      res.json(data.Item);
    } else {
      res.status(404).json({ error: 'Book not found' });
    }
  } catch (error) {
    console.error('Error in GET /books/:id:', error);
    next(error);
  }
});

module.exports = router;
