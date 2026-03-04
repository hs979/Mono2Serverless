const gremlin = require('gremlin');

/**
 * GET /recommendations
 * Get recommended books based on friends purchase history (Top 5)
 */
exports.getRecommendations = async (event, context) => {
  try {
    const neptuneEndpoint = process.env.NEPTUNE_ENDPOINT;
    
    if (!neptuneEndpoint) {
      console.warn('NEPTUNE_ENDPOINT not configured, returning empty array');
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify([])
      };
    }

    // Get user_id from pre-validated Cognito claims
    const user_id = event.requestContext?.authorizer?.claims?.sub;
    
    if (!user_id) {
      // Use fixed user ID for demo if no authenticated user
      const userId = 'us-east-1:09048fa7-0587-4963-a17e-593196775c4a';
      
      const DriverRemoteConnection = gremlin.driver.DriverRemoteConnection;
      const Graph = gremlin.structure.Graph;

      const neptuneWsEndpoint = `wss://${neptuneEndpoint}:8182/gremlin`;
      const connection = new DriverRemoteConnection(neptuneWsEndpoint, {});
      const graph = new Graph();
      const g = graph.traversal().withRemote(connection);

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

      // Close connection
      connection.close();
      
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify(recommendations)
      };
    }

    // If we have authenticated user, use their ID
    const DriverRemoteConnection = gremlin.driver.DriverRemoteConnection;
    const Graph = gremlin.structure.Graph;

    const neptuneWsEndpoint = `wss://${neptuneEndpoint}:8182/gremlin`;
    const connection = new DriverRemoteConnection(neptuneWsEndpoint, {});
    const graph = new Graph();
    const g = graph.traversal().withRemote(connection);

    // Gremlin query: Get book recommendations from user's friends purchases
    const recommendations = await g.V(user_id)
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

    // Close connection
    connection.close();
    
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
