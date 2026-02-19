/**
 * Database Initialization Script
 * Creates DynamoDB tables and initializes sample data
 */

const AWS = require('aws-sdk');
const fs = require('fs');
const path = require('path');
const { aws, dynamodb: dynamodbConfig } = require('../config');
const { dynamodb, docClient } = require('../utils/dynamodb');
const { bulkIndexBooks } = require('../utils/search-sync');


const booksTable = dynamodbConfig.booksTable;
const cartTable = dynamodbConfig.cartTable;
const ordersTable = dynamodbConfig.ordersTable;
const usersTable = dynamodbConfig.usersTable;

// Sample book data
const sampleBooks = [
  {
    id: 'book-001',
    name: 'JavaScript Advanced Programming',
    author: 'Nicholas C. Zakas',
    category: 'programming',
    price: 99.00,
    rating: 4.8,
    cover: 'https://example.com/covers/js.jpg'
  },
  {
    id: 'book-002',
    name: 'Node.js Development Guide',
    author: 'BYVoid',
    category: 'programming',
    price: 69.00,
    rating: 4.5,
    cover: 'https://example.com/covers/nodejs.jpg'
  },
  {
    id: 'book-003',
    name: 'Computer Systems: A Programmer\'s Perspective',
    author: 'Randal E. Bryant',
    category: 'computer-science',
    price: 139.00,
    rating: 4.9,
    cover: 'https://example.com/covers/csapp.jpg'
  },
  {
    id: 'book-004',
    name: 'Clean Code',
    author: 'Robert C. Martin',
    category: 'programming',
    price: 89.00,
    rating: 4.7,
    cover: 'https://example.com/covers/clean-code.jpg'
  },
  {
    id: 'book-005',
    name: 'Design Patterns',
    author: 'Erich Gamma',
    category: 'programming',
    price: 109.00,
    rating: 4.6,
    cover: 'https://example.com/covers/design-patterns.jpg'
  }
];

/**
 * Create Books Table
 */
async function createBooksTable() {
  const params = {
    TableName: booksTable,
    KeySchema: [
      { AttributeName: 'id', KeyType: 'HASH' }
    ],
    AttributeDefinitions: [
      { AttributeName: 'id', AttributeType: 'S' },
      { AttributeName: 'category', AttributeType: 'S' }
    ],
    GlobalSecondaryIndexes: [
      {
        IndexName: 'category-index',
        KeySchema: [
          { AttributeName: 'category', KeyType: 'HASH' }
        ],
        Projection: {
          ProjectionType: 'ALL'
        },
        ProvisionedThroughput: {
          ReadCapacityUnits: 5,
          WriteCapacityUnits: 5
        }
      }
    ],
    ProvisionedThroughput: {
      ReadCapacityUnits: 5,
      WriteCapacityUnits: 5
    }
  };

  try {
    await dynamodb.createTable(params).promise();
    console.log(`✓ Table ${booksTable} created successfully`);
  } catch (error) {
    if (error.code === 'ResourceInUseException') {
      console.log(`- Table ${booksTable} already exists`);
    } else {
      throw error;
    }
  }
}

/**
 * Create Cart Table
 */
async function createCartTable() {
  const params = {
    TableName: cartTable,
    KeySchema: [
      { AttributeName: 'customerId', KeyType: 'HASH' },
      { AttributeName: 'bookId', KeyType: 'RANGE' }
    ],
    AttributeDefinitions: [
      { AttributeName: 'customerId', AttributeType: 'S' },
      { AttributeName: 'bookId', AttributeType: 'S' }
    ],
    ProvisionedThroughput: {
      ReadCapacityUnits: 5,
      WriteCapacityUnits: 5
    }
  };

  try {
    await dynamodb.createTable(params).promise();
    console.log(`✓ Table ${cartTable} created successfully`);
  } catch (error) {
    if (error.code === 'ResourceInUseException') {
      console.log(`- Table ${cartTable} already exists`);
    } else {
      throw error;
    }
  }
}

/**
 * Create Orders Table
 */
async function createOrdersTable() {
  const params = {
    TableName: ordersTable,
    KeySchema: [
      { AttributeName: 'customerId', KeyType: 'HASH' },
      { AttributeName: 'orderId', KeyType: 'RANGE' }
    ],
    AttributeDefinitions: [
      { AttributeName: 'customerId', AttributeType: 'S' },
      { AttributeName: 'orderId', AttributeType: 'S' }
    ],
    ProvisionedThroughput: {
      ReadCapacityUnits: 5,
      WriteCapacityUnits: 5
    }
  };

  try {
    await dynamodb.createTable(params).promise();
    console.log(`✓ Table ${ordersTable} created successfully`);
  } catch (error) {
    if (error.code === 'ResourceInUseException') {
      console.log(`- Table ${ordersTable} already exists`);
    } else {
      throw error;
    }
  }
}

/**
 * Create Users Table
 */
async function createUsersTable() {
  const params = {
    TableName: usersTable,
    KeySchema: [
      { AttributeName: 'userId', KeyType: 'HASH' }
    ],
    AttributeDefinitions: [
      { AttributeName: 'userId', AttributeType: 'S' },
      { AttributeName: 'email', AttributeType: 'S' }
    ],
    GlobalSecondaryIndexes: [
      {
        IndexName: 'email-index',
        KeySchema: [
          { AttributeName: 'email', KeyType: 'HASH' }
        ],
        Projection: {
          ProjectionType: 'ALL'
        },
        ProvisionedThroughput: {
          ReadCapacityUnits: 5,
          WriteCapacityUnits: 5
        }
      }
    ],
    ProvisionedThroughput: {
      ReadCapacityUnits: 5,
      WriteCapacityUnits: 5
    }
  };

  try {
    await dynamodb.createTable(params).promise();
    console.log(`✓ Table ${usersTable} created successfully`);
  } catch (error) {
    if (error.code === 'ResourceInUseException') {
      console.log(`- Table ${usersTable} already exists`);
    } else {
      throw error;
    }
  }
}

/**
 * Wait for table to become ACTIVE
 */
async function waitForTable(tableName) {
  console.log(`Waiting for table ${tableName} to become ACTIVE...`);
  let isActive = false;
  
  while (!isActive) {
    try {
      const result = await dynamodb.describeTable({ TableName: tableName }).promise();
      if (result.Table.TableStatus === 'ACTIVE') {
        isActive = true;
        console.log(`✓ Table ${tableName} is ready`);
      } else {
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    } catch (error) {
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
}

/**
 * Initialize sample book data
 */
async function initializeSampleBooks() {
  console.log('Starting initialization of sample book data...');
  
  for (const book of sampleBooks) {
    const params = {
      TableName: booksTable,
      Item: book
    };

    try {
      await docClient.put(params).promise();
      console.log(`✓ Added book: ${book.name}`);
    } catch (error) {
      console.error(`✗ Failed to add book ${book.name}:`, error.message);
    }
  }
  
  console.log('✓ Sample data initialization completed');
}

/**
 * Sync book data to Elasticsearch search cluster
 */
async function syncBooksToElasticsearch() {
  console.log('Starting synchronization of book data to Elasticsearch...');
  const config = require('../config');
  if (!config.elasticsearch.enabled) {
    console.log('- Elasticsearch not enabled, skipping sync');
    return;
  }
  
  try {
    const result = await bulkIndexBooks(sampleBooks);
    
    if (result.success > 0) {
      console.log(`✓ Successfully indexed ${result.success} books to Elasticsearch`);
    }
    
    if (result.failed > 0) {
      console.warn(`⚠ Failed to index ${result.failed} books`);
    }
    
    if (result.success === 0 && result.failed === 0) {
      console.log('- No books to index');
    }
  } catch (error) {
    console.error('✗ Failed to sync to Elasticsearch:', error.message);
    console.warn('Search functionality may be unavailable, but other functions are unaffected');
  }
}

/**
 * Main function
 */
async function main() {
  console.log('========================================');
  console.log('AWS Bookstore Database Initialization');
  console.log('========================================\n');

  try {
    // Create tables
    console.log('Step 1: Create DynamoDB tables\n');
    await createBooksTable();
    await createCartTable();
    await createOrdersTable();
    await createUsersTable();

    console.log('\nStep 2: Wait for tables to be ready\n');
    await waitForTable(booksTable);
    await waitForTable(cartTable);
    await waitForTable(ordersTable);
    await waitForTable(usersTable);

    // Initialize data
    console.log('\nStep 3: Initialize sample data\n');
    await initializeSampleBooks();

    // Sync to Elasticsearch
    console.log('\nStep 4: Sync data to Elasticsearch\n');
    await syncBooksToElasticsearch();

    console.log('\n========================================');
    console.log('✓ Database initialization completed!');
    console.log('========================================');
  } catch (error) {
    console.error('\n✗ Initialization failed:', error);
    process.exit(1);
  }
}

// If dotenv is needed
try {
  require('dotenv').config();
} catch (e) {
  // dotenv might not be installed, ignore
}

// Run main function
if (require.main === module) {
  main();
}

module.exports = { main };
