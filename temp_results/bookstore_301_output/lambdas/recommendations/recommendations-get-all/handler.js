const { success, error } = require('responseHelper');
const { getUserIdFromEvent } = require('userHelper');

let gremlin = null;
let connection = null;
let g = null;

// Initialize Neptune connection
function initNeptune() {
    const neptuneEnabled = process.env.NEPTUNE_ENABLED === 'true';
    const neptuneEndpoint = process.env.NEPTUNE_ENDPOINT;
    const neptunePort = process.env.NEPTUNE_PORT || '8182';
    
    if (neptuneEnabled && neptuneEndpoint) {
        try {
            gremlin = require('gremlin');
            const DriverRemoteConnection = gremlin.driver.DriverRemoteConnection;
            const Graph = gremlin.structure.Graph;

            const endpoint = `wss://${neptuneEndpoint}:${neptunePort}/gremlin`;
            connection = new DriverRemoteConnection(endpoint, {});
            const graph = new Graph();
            g = graph.traversal().withRemote(connection);

            console.log('Neptune connection initialized');
            return g;
        } catch (err) {
            console.error('Failed to initialize Neptune:', err);
            return null;
        }
    }
    return null;
}

// Initialize on cold start
if (!g) {
    g = initNeptune();
}

exports.lambdaHandler = async (event, context) => {
    try {
        const neptuneEnabled = process.env.NEPTUNE_ENABLED === 'true';
        
        // If Neptune is not enabled or not connected, return empty array
        if (!neptuneEnabled || !g) {
            console.warn('Neptune not available, returning empty array');
            return success([]);
        }

        const userId = getUserIdFromEvent(event);

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

        return success(recommendations);
    } catch (err) {
        console.error('Error in recommendations-get-all:', err);
        // If query fails, return empty array
        return success([]);
    }
};
