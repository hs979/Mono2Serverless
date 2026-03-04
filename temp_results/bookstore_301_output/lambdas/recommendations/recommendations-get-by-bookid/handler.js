const { success, error, badRequest } = require('responseHelper');

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
        
        const bookId = event.pathParameters?.bookId;
        if (!bookId) {
            return badRequest('Missing book ID');
        }

        // If Neptune is not enabled or not connected, return mock data
        if (!neptuneEnabled || !g) {
            console.warn('Neptune not available, returning mock data');
            return success({
                friendsPurchased: [],
                purchased: 0
            });
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
            return success(result[0]);
        } else {
            return success({
                friendsPurchased: [],
                purchased: 0
            });
        }
    } catch (err) {
        console.error('Error in recommendations-get-by-bookid:', err);
        // If query fails, return default values
        return success({
            friendsPurchased: [],
            purchased: 0
        });
    }
};
