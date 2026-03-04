const { queryItems, scanItems } = require('dynamodbHelper');
const { success, error, badRequest } = require('responseHelper');

exports.lambdaHandler = async (event, context) => {
    try {
        const tableName = process.env.BOOKS_TABLE;
        if (!tableName) {
            throw new Error('BOOKS_TABLE environment variable not set');
        }

        const category = event.queryStringParameters?.category;

        if (category) {
            // Query by category
            const items = await queryItems(
                tableName,
                'category = :category',
                { ':category': category },
                'category-index'
            );
            return success(items);
        } else {
            // List all books
            const items = await scanItems(tableName);
            return success(items);
        }
    } catch (err) {
        console.error('Error in books-get-all:', err);
        return error(err.message);
    }
};
