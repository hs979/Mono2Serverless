const AWS = require('aws-sdk');
const { docClient } = require('/opt/nodejs/dynamodb-utils');

/**
 * Lambda handler for Cognito Post Confirmation trigger
 * Creates a user profile entry in UserProfiles table after successful registration
 * @param {Object} event - Cognito trigger event
 * @param {Object} context - Lambda context
 * @returns {Object} Cognito trigger response
 */
exports.lambda_handler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        // Extract user attributes from Cognito event
        const user_id = event.request.userAttributes.sub; // Cognito Sub UUID
        const email = event.request.userAttributes.email || '';
        const name = event.request.userAttributes.name || '';
        
        // Create user profile entry
        const userProfile = {
            userId: user_id,
            email: email,
            name: name,
            createdAt: new Date().toISOString()
        };
        
        const params = {
            TableName: process.env.USER_PROFILES_TABLE,
            Item: userProfile
        };
        
        await docClient.put(params).promise();
        
        console.log(`User profile created for userId: ${user_id}`);
        
        // Return the event to allow Cognito to continue
        return event;
        
    } catch (error) {
        console.error('Failed to create user profile:', error);
        // Throw error to fail the Cognito trigger
        throw new Error(`Failed to create user profile: ${error.message}`);
    }
};