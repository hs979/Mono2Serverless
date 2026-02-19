/**
 * Orders Related Routes
 * Handles order query and creation (checkout) operations
 */

const express = require('express');
const router = express.Router();
const { docClient } = require('../utils/dynamodb');
const { dynamodb } = require('../config');
const authMiddleware = require('../middleware/auth');
const { v4: uuidv4 } = require('uuid');
const { updateBestSellers } = require('../utils/bestsellers');

/**
 * GET /orders
 * List all orders for current user
 */
router.get('/', async (req, res, next) => {
  try {
    const params = {
      TableName: dynamodb.ordersTable,
      KeyConditionExpression: 'customerId = :customerId',
      ExpressionAttributeValues: {
        ':customerId': req.customerId
      }
    };

    const data = await docClient.query(params).promise();
    res.json(data.Items);
  } catch (error) {
    console.error('Error in GET /orders:', error);
    next(error);
  }
});

/**
 * POST /orders
 * Create new order (checkout process)
 * Body: { books: [{ bookId, price, quantity }, ...] }
 * 
 * This operation will:
 * 1. Create new order record
 * 2. Clear checked out items from cart
 */
router.post('/', async (req, res, next) => {
  try {
    const { books } = req.body;

    if (!books || !Array.isArray(books) || books.length === 0) {
      return res.status(400).json({ 
        error: 'Missing or invalid books array' 
      });
    }

    // Generate order ID
    const orderId = uuidv4();

    // 1. Create order
    const orderParams = {
      TableName: dynamodb.ordersTable,
      Item: {
        customerId: req.customerId,
        orderId: orderId,
        orderDate: Date.now(),
        books: books
      }
    };

    await docClient.put(orderParams).promise();

    // 2. Remove checked out items from cart
    const deletePromises = books.map(book => {
      const deleteParams = {
        TableName: dynamodb.cartTable,
        Key: {
          customerId: req.customerId,
          bookId: book.bookId
        }
      };
      return docClient.delete(deleteParams).promise();
    });

    await Promise.all(deletePromises);

    // 3. Sync update bestsellers (executed asynchronously, not blocking response)
    // Update logic runs in background
    updateBestSellers(books).then(result => {
      if (result.success > 0) {
        console.log(`Bestseller updated: ${result.success} books`);
      }
      if (result.failed > 0) {
        console.warn(`Bestseller update failed for ${result.failed} books`);
      }
    }).catch(error => {
      // Bestseller update failure should not affect order creation
      console.error('Error updating bestsellers:', error);
    });

    res.json({ 
      message: 'Order created successfully',
      orderId: orderId
    });
  } catch (error) {
    console.error('Error in POST /orders:', error);
    next(error);
  }
});

module.exports = router;
