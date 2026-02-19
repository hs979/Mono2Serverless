/**
 * Recommendation System Routes
 * Provides book recommendations based on social graph
 * Uses Neptune graph database (optional) or returns mock data
 */

const express = require('express');
const router = express.Router();
const config = require('../config');

// Neptune Gremlin Client (Optional)
let gremlin = null;
let connection = null;

// Try to initialize Neptune connection
function initNeptune() {
  if (config.neptune.enabled && config.neptune.endpoint) {
    try {
      gremlin = require('gremlin');
      const DriverRemoteConnection = gremlin.driver.DriverRemoteConnection;
      const Graph = gremlin.structure.Graph;

      const neptuneEndpoint = `wss://${config.neptune.endpoint}:${config.neptune.port}/gremlin`;
      connection = new DriverRemoteConnection(neptuneEndpoint, {});
      const graph = new Graph();
      const g = graph.traversal().withRemote(connection);

      console.log('Neptune connection initialized');
      return g;
    } catch (error) {
      console.error('Failed to initialize Neptune:', error);
      return null;
    }
  }
  return null;
}

const g = initNeptune();

/**
 * GET /recommendations
 * Get recommended books based on friends purchase history (Top 5)
 */
router.get('/', async (req, res, next) => {
  try {
    // If Neptune is not enabled or not connected, return mock data
    if (!config.neptune.enabled || !g) {
      console.warn('Neptune not available, returning mock data');
      return res.json([]);
    }

    // Use fixed user ID for query
    // In real app, should use req.customerId
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

    res.json(recommendations);
  } catch (error) {
    console.error('Error in GET /recommendations:', error);
    // If query fails, return empty array
    res.json([]);
  }
});

/**
 * GET /recommendations/:bookId
 * Get list of friends who purchased a specific book and purchase count
 * Path params: bookId - Book ID
 */
router.get('/:bookId', async (req, res, next) => {
  try {
    const bookId = req.params.bookId;

    // If Neptune is not enabled or not connected, return mock data
    if (!config.neptune.enabled || !g) {
      console.warn('Neptune not available, returning mock data');
      return res.json({
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
      res.json(result[0]);
    } else {
      res.json({
        friendsPurchased: [],
        purchased: 0
      });
    }
  } catch (error) {
    console.error('Error in GET /recommendations/:bookId:', error);
    // If query fails, return default values
    res.json({
      friendsPurchased: [],
      purchased: 0
    });
  }
});

module.exports = router;
