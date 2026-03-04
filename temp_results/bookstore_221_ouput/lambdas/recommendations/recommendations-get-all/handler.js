/**
 * Lambda handler for GET /recommendations
 * Get recommended books based on friends purchase history (Top 5)
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
        
        // If Neptune is not enabled or not connected, return empty array
        if (!NEPTUNE_ENABLED || !g) {
            console.warn('Neptune not available, returning empty array');
            return {
                statusCode: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                body: JSON.stringify([])
            };
        }

        // Use fixed user ID for query
        // In real app, should use authenticated user ID
        const userId = 'us-east-1:09048fa7-0587-4963-a17e-593196775c4a';

        // Gremlin query: Get book recommendations from user's friends purchases
        const recommendations = await g.V(userId)
            .out('friendOf')
            .aggregate('friends')
            .barrier()
            .out('purchased')
            .dedup()
            .project('bookId', 'purchases', 'friendsPurchased')
                .by(gremlin.process.id)
                .by(gremlin.process.in_('purchased').where(gremlin.process.P.within('friends')).count())
                .by(gremlin.process.in_('purchased').where(gremlin.process.P.within('friends')).id().fold())
            .order()
                .by('purchases', gremlin.process.order.desc)
            .limit(5)
            .toList();

        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify(recommendations)
        };
    } catch (error) {
        console.error('Error in GET /recommendations:', error);
        // If query fails, return empty array
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify([])
        };
    }
};
