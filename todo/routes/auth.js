const express = require('express');
const bcrypt = require('bcryptjs');
const { docClient, tables } = require('../config/db');
const { generateToken } = require('../utils/jwt');

const router = express.Router();

router.post('/register', async (req, res) => {
  try {
    const { username, password, email } = req.body;

    if (!username || !password) {
      return res.status(400).json({
        message: 'Username and password cannot be empty'
      });
    }

    if (password.length < 6) {
      return res.status(400).json({
        message: 'Password must be at least 6 characters long'
      });
    }

    const checkParams = {
      TableName: tables.USER_TABLE,
      Key: { username }
    };

    const existingUser = await docClient.get(checkParams).promise();
    
    if (existingUser.Item) {
      return res.status(400).json({
        message: 'Username already exists, please choose another username'
      });
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    const user = {
      username,
      password: hashedPassword,
      email: email || '',
      createdAt: new Date().toISOString()
    };

    const putParams = {
      TableName: tables.USER_TABLE,
      Item: user
    };

    await docClient.put(putParams).promise();

    const token = generateToken(username);

    res.status(201).json({
      message: 'Registration successful',
      token,
      username
    });

  } catch (error) {
    console.error('Registration failed:', error);
    res.status(500).json({
      message: 'Registration failed, please try again later',
      error: error.message
    });
  }
});

router.post('/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({
        message: 'Username and password cannot be empty'
      });
    }

    const params = {
      TableName: tables.USER_TABLE,
      Key: { username }
    };

    const result = await docClient.get(params).promise();
    const user = result.Item;

    if (!user) {
      return res.status(401).json({
        message: 'Invalid username or password'
      });
    }

    const isPasswordValid = await bcrypt.compare(password, user.password);

    if (!isPasswordValid) {
      return res.status(401).json({
        message: 'Invalid username or password'
      });
    }

    const token = generateToken(username);

    res.json({
      message: 'Login successful',
      token,
      username
    });

  } catch (error) {
    console.error('Login failed:', error);
    res.status(500).json({
      message: 'Login failed, please try again later',
      error: error.message
    });
  }
});

module.exports = router;

