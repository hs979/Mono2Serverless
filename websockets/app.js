// Implements connection management and message broadcasting

const WebSocket = require('ws');
const PORT = process.env.PORT || 8080;

// Store all active WebSocket connections
// Key: connectionId (auto-incrementing ID), Value: WebSocket connection object
const connections = new Map();
let connectionIdCounter = 0;

/**
 * Create WebSocket server
 */
const wss = new WebSocket.Server({ port: PORT });

/**
 * Handle new WebSocket connections
 */
wss.on('connection', (ws) => {
  // Generate unique connection ID
  const connectionId = ++connectionIdCounter;
  
  // Store connection in Map
  connections.set(connectionId, ws);
  
  console.log(`[Connection] New client connected, connectionId: ${connectionId}, current online users: ${connections.size}`);
  
  /**
   * Handle messages sent by client
   */
  ws.on('message', (message) => {
    try {
      // Parse message
      const parsedMessage = JSON.parse(message);
      console.log(`[Message] Received message from connectionId ${connectionId}:`, parsedMessage);
      
      // Check action type
      if (parsedMessage.action === 'sendmessage' && parsedMessage.data) {
        const messageData = parsedMessage.data;
        
        // Broadcast message to all connected clients
        let successCount = 0;
        let failCount = 0;
        
        connections.forEach((clientWs, clientId) => {
          // Check if connection is valid
          if (clientWs.readyState === WebSocket.OPEN) {
            try {
              // Send message data
              clientWs.send(messageData);
              successCount++;
            } catch (error) {
              console.error(`[Error] Failed to send message to connectionId ${clientId}:`, error.message);
              failCount++;
            }
          } else {
            // Clean up invalid connections
            connections.delete(clientId);
            console.log(`[Cleanup] Removed invalid connection connectionId: ${clientId}`);
            failCount++;
          }
        });
        
        console.log(`[Broadcast] Message sent - Success: ${successCount}, Failed: ${failCount}`);
      } else {
        console.log(`[Warning] Unknown message format or missing required fields:`, parsedMessage);
      }
    } catch (error) {
      console.error(`[Error] Error processing message:`, error.message);
    }
  });
  
  /**
   * Handle client disconnection
   */
  ws.on('close', () => {
    // Remove connection from Map
    connections.delete(connectionId);
    console.log(`[Disconnect] connectionId ${connectionId} disconnected, current online users: ${connections.size}`);
  });
  
  /**
   * Handle connection errors
   */
  ws.on('error', (error) => {
    console.error(`[Error] Error occurred in connectionId ${connectionId}:`, error.message);
    // Also remove connection on error
    connections.delete(connectionId);
  });
});

/**
 * Server started successfully
 */
wss.on('listening', () => {
  console.log(`==============================================`);
  console.log(`WebSocket Chat Server Started`);
  console.log(`Listening on port: ${PORT}`);
  console.log(`Connection address: ws://localhost:${PORT}`);
  console.log(`==============================================`);
});

/**
 * Server error handling
 */
wss.on('error', (error) => {
  console.error('[Fatal Error] WebSocket server error:', error);
  process.exit(1);
});

/**
 * Graceful shutdown handling
 */
process.on('SIGINT', () => {
  console.log('\nShutting down server...');
  
  // Close all client connections
  connections.forEach((ws, connectionId) => {
    ws.close();
    console.log(`Closing connection: ${connectionId}`);
  });
  
  // Close WebSocket server
  wss.close(() => {
    console.log('Server closed');
    process.exit(0);
  });
});
