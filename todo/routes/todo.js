const express = require('express');
const { v1: uuidv1 } = require('uuid');
const { docClient, tables } = require('../config/db');
const { authenticateToken } = require('../middleware/auth');

const router = express.Router();

router.use(authenticateToken);

router.get('/item', async (req, res) => {
  try {
    const username = req.user.username;

    const params = {
      TableName: tables.TODO_TABLE,
      KeyConditionExpression: "#username = :username",
      ExpressionAttributeNames: {
        "#username": "cognito-username"
      },
      ExpressionAttributeValues: {
        ":username": username
      }
    };

    const result = await docClient.query(params).promise();

    res.json({
      Items: result.Items || [],
      Count: result.Count || 0
    });

  } catch (error) {
    console.error('Failed to fetch todo list:', error);
    res.status(400).json({
      message: error.message
    });
  }
});

router.get('/item/:id', async (req, res) => {
  try {
    const username = req.user.username;
    const { id } = req.params;

    if (!id || !/^[\w-]+$/.test(id)) {
      return res.status(400).json({
        message: 'Invalid request: Invalid todo item ID'
      });
    }

    const params = {
      TableName: tables.TODO_TABLE,
      Key: {
        "cognito-username": username,
        id: id
      }
    };

    const result = await docClient.get(params).promise();

    if (!result.Item) {
      return res.status(404).json({
        message: 'Todo item not found'
      });
    }

    res.json(result);

  } catch (error) {
    console.error('Failed to fetch todo item:', error);
    res.status(400).json({
      message: error.message
    });
  }
});

router.post('/item', async (req, res) => {
  try {
    const username = req.user.username;
    const { item, completed } = req.body;

    if (!item) {
      return res.status(400).json({
        message: 'Invalid request: Todo item content cannot be empty'
      });
    }
    const now = new Date().toISOString();
    const todoItem = {
      "cognito-username": username,
      id: uuidv1(),
      item: item,
      completed: completed || false,
      creation_date: now,
      lastupdate_date: now
    };

    const params = {
      TableName: tables.TODO_TABLE,
      Item: todoItem
    };

    await docClient.put(params).promise();

    res.json({
      message: 'Todo item created successfully',
      item: todoItem
    });

  } catch (error) {
    console.error('Failed to create todo item:', error);
    res.status(400).json({
      message: error.message
    });
  }
});

router.put('/item/:id', async (req, res) => {
  try {
    const username = req.user.username;
    const { id } = req.params;
    const { item, completed } = req.body;

    if (!id || !/^[\w-]+$/.test(id)) {
      return res.status(400).json({
        message: 'Invalid request: Invalid todo item ID'
      });
    }

    if (item === undefined || completed === undefined) {
      return res.status(400).json({
        message: 'Invalid request: Missing required fields'
      });
    }
    const params = {
      TableName: tables.TODO_TABLE,
      Key: {
        "cognito-username": username,
        id: id
      },
      UpdateExpression: "set completed = :c, lastupdate_date = :lud, #i = :i",
      ExpressionAttributeNames: {
        "#i": "item"
      },
      ExpressionAttributeValues: {
        ":c": completed,
        ":lud": new Date().toISOString(),
        ":i": item
      },
      ReturnValues: "ALL_NEW"
    };

    const result = await docClient.update(params).promise();

    res.json({
      message: 'Todo item updated successfully',
      Attributes: result.Attributes
    });

  } catch (error) {
    console.error('Failed to update todo item:', error);
    res.status(400).json({
      message: error.message
    });
  }
});

router.post('/item/:id/done', async (req, res) => {
  try {
    const username = req.user.username;
    const { id } = req.params;

    if (!id || !/^[\w-]+$/.test(id)) {
      return res.status(400).json({
        message: 'Invalid request: Invalid todo item ID'
      });
    }
    const params = {
      TableName: tables.TODO_TABLE,
      Key: {
        "cognito-username": username,
        id: id
      },
      UpdateExpression: "set #field = :value",
      ExpressionAttributeNames: {
        "#field": "completed"
      },
      ExpressionAttributeValues: {
        ":value": true
      },
      ReturnValues: "ALL_NEW"
    };

    const result = await docClient.update(params).promise();

    res.json({
      message: 'Todo item marked as completed',
      Attributes: result.Attributes
    });

  } catch (error) {
    console.error('Failed to mark todo item as completed:', error);
    res.status(400).json({
      message: error.message
    });
  }
});

router.delete('/item/:id', async (req, res) => {
  try {
    const username = req.user.username;
    const { id } = req.params;

    if (!id || !/^[\w-]+$/.test(id)) {
      return res.status(400).json({
        message: 'Invalid request: Invalid todo item ID'
      });
    }
    const params = {
      TableName: tables.TODO_TABLE,
      Key: {
        "cognito-username": username,
        id: id
      }
    };

    await docClient.delete(params).promise();

    res.json({
      message: 'Todo item deleted successfully'
    });

  } catch (error) {
    console.error('Failed to delete todo item:', error);
    res.status(400).json({
      message: error.message
    });
  }
});

module.exports = router;

