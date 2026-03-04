const { deleteItem } = require('dynamodbHelper');
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
        const { bookId } = body;

        if (!bookId) {
            return badRequest('Missing required field: bookId');
        }

        const key = {
            customerId: userId,
            bookId: bookId
        };
        
        await deleteItem(tableName, key);
        return success({ message: 'Item removed from cart successfully' });
    } catch (err) {
        console.error('Error in cart-delete-item:', err);
        return error(err.message);
    }
};
