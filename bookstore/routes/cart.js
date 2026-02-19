/**
 * Cart Related Routes
 * Handles CRUD operations for shopping cart
 */

const express = require('express');
const router = express.Router();
const { docClient } = require('../utils/dynamodb');
const { dynamodb } = require('../config');
const authMiddleware = require('../middleware/auth');
const { v4: uuidv4 } = require('uuid');

/**
 * GET /cart
 * List all items in current user's cart
 */
router.get('/', async (req, res, next) => {
  try {
    const params = {
      TableName: dynamodb.cartTable,
      KeyConditionExpression: 'customerId = :customerId',
      ExpressionAttributeValues: {
        ':customerId': req.customerId
      }
    };

    const data = await docClient.query(params).promise();
    res.json(data.Items);
  } catch (error) {
    console.error('Error in GET /cart:', error);
    next(error);
  }
});

/**
 * GET /cart/:bookId
 * Get specific book info in cart
 * Path params: bookId - Book ID
 */
router.get('/:bookId', async (req, res, next) => {
  try {
    const params = {
      TableName: dynamodb.cartTable,
      Key: {
        customerId: req.customerId,
        bookId: req.params.bookId
      }
    };

    const data = await docClient.get(params).promise();
    
    if (data.Item) {
      res.json(data.Item);
    } else {
      res.status(404).json({ error: 'Item not found in cart' });
    }
  } catch (error) {
    console.error('Error in GET /cart/:bookId:', error);
    next(error);
  }
});

/**
 * POST /cart
 * Add book to cart
 * Body: { bookId, quantity, price }
 */
router.post('/', async (req, res, next) => {
  try {
    const { bookId, quantity, price } = req.body;

    if (!bookId || !quantity || !price) {
      return res.status(400).json({ 
        error: 'Missing required fields: bookId, quantity, price' 
      });
    }

    const params = {
      TableName: dynamodb.cartTable,
      Item: {
        customerId: req.customerId,
        bookId: bookId,
        quantity: quantity,
        price: price
      }
    };

    await docClient.put(params).promise();
    res.json({ message: 'Item added to cart successfully' });
  } catch (error) {
    console.error('Error in POST /cart:', error);
    next(error);
  }
});

/**
 * PUT /cart
 * Update book quantity in cart
 * Body: { bookId, quantity }
 */
router.put('/', async (req, res, next) => {
  try {
    const { bookId, quantity } = req.body;

    if (!bookId || !quantity) {
      return res.status(400).json({ 
        error: 'Missing required fields: bookId, quantity' 
      });
    }

    const params = {
      TableName: dynamodb.cartTable,
      Key: {
        customerId: req.customerId,
        bookId: bookId
      },
      UpdateExpression: 'SET quantity = :quantity',
      ExpressionAttributeValues: {
        ':quantity': quantity
      },
      ReturnValues: 'ALL_NEW'
    };

    await docClient.update(params).promise();
    res.json({ message: 'Cart updated successfully' });
  } catch (error) {
    console.error('Error in PUT /cart:', error);
    next(error);
  }
});

/**
 * DELETE /cart
 * Remove book from cart
 * Body: { bookId }
 */
router.delete('/', async (req, res, next) => {
  try {
    const { bookId } = req.body;

    if (!bookId) {
      return res.status(400).json({ 
        error: 'Missing required field: bookId' 
      });
    }

    const params = {
      TableName: dynamodb.cartTable,
      Key: {
        customerId: req.customerId,
        bookId: bookId
      }
    };

    await docClient.delete(params).promise();
    res.json({ message: 'Item removed from cart successfully' });
  } catch (error) {
    console.error('Error in DELETE /cart:', error);
    next(error);
  }
});

module.exports = router;
