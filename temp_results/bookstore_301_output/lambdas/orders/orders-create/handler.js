const { putItem, deleteItem } = require('dynamodbHelper');
const { getUserIdFromEvent } = require('userHelper');
const { invokeLambda } = require('internalClient');
const { success, error, badRequest } = require('responseHelper');
const { v4: uuidv4 } = require('uuid');

exports.lambdaHandler = async (event, context) => {
    try {
        const ordersTable = process.env.ORDERS_TABLE;
        const cartTable = process.env.CART_TABLE;
        const bestsellersUpdateFunctionName = process.env.BESTSELLERS_UPDATE_FUNCTION_NAME;
        
        if (!ordersTable || !cartTable) {
            throw new Error('Missing required environment variables');
        }

        const userId = getUserIdFromEvent(event);
        
        if (!event.body) {
            return badRequest('Missing request body');
        }
        
        const body = JSON.parse(event.body);
        const { books } = body;

        if (!books || !Array.isArray(books) || books.length === 0) {
            return badRequest('Missing or invalid books array');
        }

        // Generate order ID
        const orderId = uuidv4();

        // 1. Create order
        const orderItem = {
            customerId: userId,
            orderId: orderId,
            orderDate: Date.now(),
            books: books
        };

        await putItem(ordersTable, orderItem);

        // 2. Remove checked out items from cart
        const deletePromises = books.map(book => {
            const key = {
                customerId: userId,
                bookId: book.bookId
            };
            return deleteItem(cartTable, key);
        });

        await Promise.all(deletePromises);

        // 3. Call bestsellers-update Lambda asynchronously (fire-and-forget)
        if (bestsellersUpdateFunctionName) {
            // Prepare payload for bestsellers update
            const bestsellersPayload = books.map(book => ({
                bookId: book.bookId,
                quantity: book.quantity
            }));
            
            // Invoke asynchronously (Event)
            invokeLambda(bestsellersUpdateFunctionName, bestsellersPayload, 'Event')
                .then(() => {
                    console.log(`Bestseller update triggered for ${bestsellersPayload.length} books`);
                })
                .catch(err => {
                    // Log error but don't fail the order
                    console.error('Error triggering bestseller update:', err);
                });
        }

        return success({ 
            message: 'Order created successfully',
            orderId: orderId
        });
    } catch (err) {
        console.error('Error in orders-create:', err);
        return error(err.message);
    }
};
