const { putItem } = require('dynamodbHelper');
const { success, error } = require('responseHelper');

exports.lambdaHandler = async (event, context) => {
    try {
        const tableName = process.env.USER_PROFILES_TABLE;
        if (!tableName) {
            throw new Error('USER_PROFILES_TABLE environment variable not set');
        }

        // Cognito Post-Confirmation event structure
        // event.request.userAttributes contains user attributes
        const userAttributes = event.request.userAttributes;
        const userId = userAttributes.sub; // Cognito UUID
        const email = userAttributes.email;
        const name = userAttributes.name || email.split('@')[0];
        
        // Create user profile item
        const item = {
            userId: userId,
            email: email,
            name: name,
            createdAt: Date.now(),
            updatedAt: Date.now()
        };

        await putItem(tableName, item);
        
        console.log(`User profile created for ${email} with userId ${userId}`);
        
        // Return the event to allow Cognito to continue
        return event;
    } catch (err) {
        console.error('Error in user-post-confirmation:', err);
        // Do not throw error; Cognito expects the event to be returned
        // Log error and continue
        return event;
    }
};
