require('dotenv').config();
const AWS = require('aws-sdk');

const awsConfig = {
  region: process.env.AWS_REGION || 'us-east-1'
};

if (process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY) {
  awsConfig.accessKeyId = process.env.AWS_ACCESS_KEY_ID;
  awsConfig.secretAccessKey = process.env.AWS_SECRET_ACCESS_KEY;
}

const dynamodb = new AWS.DynamoDB(awsConfig);

const TODO_TABLE = process.env.TODO_TABLE_NAME || 'todo-monolith-table';
const USER_TABLE = process.env.USER_TABLE_NAME || 'todo-monolith-users';

async function tableExists(tableName) {
  try {
    await dynamodb.describeTable({ TableName: tableName }).promise();
    return true;
  } catch (error) {
    if (error.code === 'ResourceNotFoundException') {
      return false;
    }
    throw error;
  }
}

async function waitForTable(tableName) {
  console.log(`  Waiting for table ${tableName} to become ACTIVE...`);
  let attempts = 0;
  const maxAttempts = 30;
  
  while (attempts < maxAttempts) {
    try {
      const result = await dynamodb.describeTable({ TableName: tableName }).promise();
      const status = result.Table.TableStatus;
      
      if (status === 'ACTIVE') {
        console.log(`  ✓ Table ${tableName} is ready`);
        return true;
      }
      
      process.stdout.write('.');
      await new Promise(resolve => setTimeout(resolve, 2000));
      attempts++;
    } catch (error) {
      console.error(`\n  ✗ Error checking table status: ${error.message}`);
      return false;
    }
  }
  
  console.log(`\n  ✗ Timeout waiting for table`);
  return false;
}

async function createTodoTable() {
  const params = {
    TableName: TODO_TABLE,
    KeySchema: [
      { AttributeName: 'cognito-username', KeyType: 'HASH' },
      { AttributeName: 'id', KeyType: 'RANGE' }
    ],
    AttributeDefinitions: [
      { AttributeName: 'cognito-username', AttributeType: 'S' },
      { AttributeName: 'id', AttributeType: 'S' }
    ],
    BillingMode: 'PAY_PER_REQUEST',
    Tags: [
      { Key: 'Application', Value: 'TodoMonolith' },
      { Key: 'Environment', Value: process.env.NODE_ENV || 'development' }
    ]
  };

  try {
    if (await tableExists(TODO_TABLE)) {
      console.log(`- Table ${TODO_TABLE} already exists, skipping creation`);
      return false;
    }

    await dynamodb.createTable(params).promise();
    console.log(`✓ Table ${TODO_TABLE} created successfully`);
    console.log(`  Partition key: cognito-username (String)`);
    console.log(`  Sort key: id (String)`);
    return true;
  } catch (error) {
    if (error.code === 'ResourceInUseException') {
      console.log(`- Table ${TODO_TABLE} already exists`);
      return false;
    }
    throw error;
  }
}

async function createUserTable() {
  const params = {
    TableName: USER_TABLE,
    KeySchema: [
      { AttributeName: 'username', KeyType: 'HASH' }
    ],
    AttributeDefinitions: [
      { AttributeName: 'username', AttributeType: 'S' }
    ],
    BillingMode: 'PAY_PER_REQUEST',
    Tags: [
      { Key: 'Application', Value: 'TodoMonolith' },
      { Key: 'Environment', Value: process.env.NODE_ENV || 'development' }
    ]
  };

  try {
    if (await tableExists(USER_TABLE)) {
      console.log(`- Table ${USER_TABLE} already exists, skipping creation`);
      return false;
    }

    await dynamodb.createTable(params).promise();
    console.log(`✓ Table ${USER_TABLE} created successfully`);
    console.log(`  Primary key: username (String)`);
    return true;
  } catch (error) {
    if (error.code === 'ResourceInUseException') {
      console.log(`- Table ${USER_TABLE} already exists`);
      return false;
    }
    throw error;
  }
}

async function main() {
  console.log('========================================');
  console.log('Todo Application - DynamoDB Table Initialization');
  console.log('========================================');
  console.log(`Region: ${awsConfig.region}`);
  if (awsConfig.endpoint) {
    console.log(`Endpoint: ${awsConfig.endpoint} (local mode)`);
  }
  console.log('');

  try {
    console.log('Step 1: Creating DynamoDB tables');
    console.log('');
    
    const todoCreated = await createTodoTable();
    const userCreated = await createUserTable();
    
    if (todoCreated || userCreated) {
      console.log('');
      console.log('Step 2: Waiting for tables to be created');
      console.log('');
      
      if (todoCreated) {
        await waitForTable(TODO_TABLE);
      }
      if (userCreated) {
        await waitForTable(USER_TABLE);
      }
    }

    console.log('');
    console.log('========================================');
    console.log('✓ Database initialization completed!');
    console.log('========================================');
    console.log('');
    console.log('Created tables:');
    console.log(`  1. ${TODO_TABLE} - Todo items table`);
    console.log(`  2. ${USER_TABLE} - Users table`);
    console.log('');
    console.log('You can now start the application:');
    console.log('  cd backend && npm start');
    console.log('');

  } catch (error) {
    console.error('');
    console.error('========================================');
    console.error('✗ Initialization failed!');
    console.error('========================================');
    console.error('Error message:', error.message);
    console.error('');
    
    if (error.code === 'CredentialsError' || error.code === 'InvalidClientTokenId') {
      console.error('Tip: Please check AWS credentials configuration');
      console.error('  1. Run aws configure');
      console.error('  2. Or configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env file');
    } else if (error.code === 'NetworkingError') {
      console.error('Tip: Network connection failed, please check network settings and AWS region configuration');
    }
    
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  createTodoTable,
  createUserTable,
  tableExists,
  main
};
