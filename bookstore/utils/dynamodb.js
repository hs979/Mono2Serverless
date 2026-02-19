const AWS = require('aws-sdk');
const config = require('../config');

const awsConfig = {
  region: config.aws.region,
  accessKeyId: config.aws.accessKeyId,
  secretAccessKey: config.aws.secretAccessKey
};

const dynamodb = new AWS.DynamoDB(awsConfig);
const docClient = new AWS.DynamoDB.DocumentClient({ service: dynamodb });

module.exports = {
  dynamodb,
  docClient,
};
