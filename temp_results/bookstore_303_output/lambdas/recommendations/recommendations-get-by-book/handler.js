const gremlin = require('gremlin');

/**
 * GET /recommendations/{bookId}
 * Get list of friends who purchased a specific book and purchase count
 */
exports.getBookRecommendations = async (event, context) => {
  try {
    const neptuneEndpoint = process.env.NEPTUNE_ENDPOINT;
    const bookId = event.pathParameters?.bookId;
    
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

    if (!neptuneEndpoint) {
      console.warn('NEPTUNE_ENDPOINT not configured, returning mock data');
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

    const DriverRemoteConnection = gremlin.driver.DriverRemoteConnection;
    const Graph = gremlin.structure.Graph;

    const neptuneWsEndpoint = `wss://${neptuneEndpoint}:8182/gremlin`;
    const connection = new DriverRemoteConnection(neptuneWsEndpoint, {});
    const graph = new Graph();
    const g = graph.traversal().withRemote(connection);

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

    // Close connection
    connection.close();

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
