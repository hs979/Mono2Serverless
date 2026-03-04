const { getItem } = require('dynamodbHelper');
const { getUserIdFromEvent } = require('userHelper');
const { success, error, notFound, badRequest } = require('responseHelper');

exports.lambdaHandler = async (event, context) => {
    try {
        const tableName = process.env.CART_TABLE;
        if (!tableName) {
            throw new Error('CART_TABLE environment variable not set');
        }

        const userId = getUserIdFromEvent(event);
        const bookId = event.pathParameters?.bookId;
        if (!bookId) {
            return badRequest('Missing book ID');
        }

        const key = {
            customerId: userId,
            bookId: bookId
        };
        const item = await getItem(tableName, key);
        
        if (item) {
            return success(item);
        } else {
            return notFound('Item not found in cart');
        }
    } catch (err) {
        console.error('Error in cart-get-by-bookid:', err);
        return error(err.message);
    }
};
