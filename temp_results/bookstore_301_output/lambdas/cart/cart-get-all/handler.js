const { queryItems } = require('dynamodbHelper');
const { getUserIdFromEvent } = require('userHelper');
const { success, error } = require('responseHelper');

exports.lambdaHandler = async (event, context) => {
    try {
        const tableName = process.env.CART_TABLE;
        if (!tableName) {
            throw new Error('CART_TABLE environment variable not set');
        }

        const userId = getUserIdFromEvent(event);

        const items = await queryItems(
            tableName,
            'customerId = :customerId',
            { ':customerId': userId }
        );
        
        return success(items);
    } catch (err) {
        console.error('Error in cart-get-all:', err);
        return error(err.message);
    }
};
