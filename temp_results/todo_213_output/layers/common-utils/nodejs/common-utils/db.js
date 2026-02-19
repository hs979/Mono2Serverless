const AWS = require('aws-sdk');

/**
 * Shared DynamoDB DocumentClient for Lambda functions.
 * AWS SDK is automatically configured with Lambda execution role.
 */
const docClient = new AWS.DynamoDB.DocumentClient();

/**
 * Get table name from environment variable.
 * @returns {string} Table name for Todo items
 */
function getTodoTableName() {
  return process.env.TODO_TABLE;
}

module.exports = {
  docClient,
  getTodoTableName
};
