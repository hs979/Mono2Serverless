const { getItem } = require('dynamodbHelper');
const { success, error, notFound, badRequest } = require('responseHelper');

exports.lambdaHandler = async (event, context) => {
    try {
        const tableName = process.env.BOOKS_TABLE;
        if (!tableName) {
            throw new Error('BOOKS_TABLE environment variable not set');
        }

        const bookId = event.pathParameters?.id;
        if (!bookId) {
            return badRequest('Missing book ID');
        }

        const key = { id: bookId };
        const item = await getItem(tableName, key);
        
        if (item) {
            return success(item);
        } else {
            return notFound('Book not found');
        }
    } catch (err) {
        console.error('Error in books-get-by-id:', err);
        return error(err.message);
    }
};
