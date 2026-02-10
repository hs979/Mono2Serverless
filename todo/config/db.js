const AWS = require('aws-sdk');

AWS.config.update({
  region: process.env.AWS_REGION || 'us-east-1'
});

if (process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY) {
  AWS.config.update({
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  });
}

const options = {
  region: process.env.AWS_REGION || 'us-east-1'
};

const docClient = new AWS.DynamoDB.DocumentClient(options);

const tables = {
  TODO_TABLE: process.env.TODO_TABLE_NAME || 'todo-monolith-table',
  USER_TABLE: process.env.USER_TABLE_NAME || 'todo-monolith-users'
};

module.exports = {
  docClient,
  tables
};

