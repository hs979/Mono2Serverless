const { updateItem } = require('dynamodbHelper');
const { getUserIdFromEvent } = require('userHelper');
const { success, error, badRequest } = require('responseHelper');

exports.lambdaHandler = async (event, context) => {
    try {
        const tableName = process.env.CART_TABLE;
        if (!tableName) {
            throw new Error('CART_TABLE environment variable not set');
        }

        const userId = getUserIdFromEvent(event);
        
        if (!event.body) {
            return badRequest('Missing request body');
        }
        
        const body = JSON.parse(event.body);
        const { bookId, quantity } = body;

        if (!bookId || !quantity) {
            return badRequest('Missing required fields: bookId, quantity');
        }

        const key = {
            customerId: userId,
            bookId: bookId
        };
        
        const updatedAttributes = await updateItem(
            tableName,
            key,
            'SET quantity = :quantity',
            { ':quantity': quantity }
        );
        
        return success({ message: 'Cart updated successfully' });
    } catch (err) {
        console.error('Error in cart-update-item:', err);
        return error(err.message);
    }
};
