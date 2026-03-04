/**
 * Lambda handler for GET /recommendations/{bookId}
 * Get list of friends who purchased a specific book and purchase count
 */

let gremlin = null;
let connection = null;
let g = null;

// Initialize Neptune connection
function initNeptune() {
    const NEPTUNE_ENABLED = process.env.NEPTUNE_ENABLED === 'true' || process.env.NEPTUNE_ENABLED === '1';
    const NEPTUNE_ENDPOINT = process.env.NEPTUNE_ENDPOINT;
    const NEPTUNE_PORT = process.env.NEPTUNE_PORT || 8182;
    
    if (NEPTUNE_ENABLED && NEPTUNE_ENDPOINT) {
        try {
            gremlin = require('gremlin');
            const DriverRemoteConnection = gremlin.driver.DriverRemoteConnection;
            const Graph = gremlin.structure.Graph;

            const neptuneEndpoint = `wss://${NEPTUNE_ENDPOINT}:${NEPTUNE_PORT}/gremlin`;
            connection = new DriverRemoteConnection(neptuneEndpoint, {});
            const graph = new Graph();
            g = graph.traversal().withRemote(connection);

            console.log('Neptune connection initialized');
            return g;
        } catch (error) {
            console.error('Failed to initialize Neptune:', error);
            return null;
        }
    }
    return null;
}

// Initialize Neptune on cold start
if (!g) {
    g = initNeptune();
}

exports.lambdaHandler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const NEPTUNE_ENABLED = process.env.NEPTUNE_ENABLED === 'true' || process.env.NEPTUNE_ENABLED === '1';
        const bookId = event.pathParameters ? event.pathParameters.bookId : null;
        
        if (!bookId) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({ error: 'Book ID is required' })
            };
        }

        // If Neptune is not enabled or not connected, return mock data
        if (!NEPTUNE_ENABLED || !g) {
            console.warn('Neptune not available, returning mock data');
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({
                    friendsPurchased: [],
                    purchased: 0
                })
            };
        }

        // Gremlin query: Get friends who purchased this book
        const result = await g.V(bookId)
            .project('friendsPurchased', 'purchased')
                .by(gremlin.process.in_('purchased')
                    .dedup()
                    .where(gremlin.process.id().is(gremlin.process.P.neq(bookId)))
                    .id()
                    .fold())
                .by(gremlin.process.in_('purchased').count())
            .toList();

        if (result && result.length > 0) {
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify(result[0])
            };
        } else {
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify({
                    friendsPurchased: [],
                    purchased: 0
                })
            };
        }
    } catch (error) {
        console.error('Error in GET /recommendations/{bookId}:', error);
        // If query fails, return default values
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                friendsPurchased: [],
                purchased: 0
            })
        };
    }
};
