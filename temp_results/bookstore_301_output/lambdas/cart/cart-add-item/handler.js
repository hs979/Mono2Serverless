const { putItem } = require('dynamodbHelper');
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
        const { bookId, quantity, price } = body;

        if (!bookId || !quantity || !price) {
            return badRequest('Missing required fields: bookId, quantity, price');
        }

        const item = {
            customerId: userId,
            bookId: bookId,
            quantity: quantity,
            price: price
        };

        await putItem(tableName, item);
        return success({ message: 'Item added to cart successfully' });
    } catch (err) {
        console.error('Error in cart-add-item:', err);
        return error(err.message);
    }
};
