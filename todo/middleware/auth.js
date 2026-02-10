const { verifyToken } = require('../utils/jwt');

function authenticateToken(req, res, next) {

  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.startsWith('Bearer ')
    ? authHeader.substring(7)
    : authHeader;

  if (!token) {
    return res.status(401).json({
      message: 'No authentication token provided. Please log in first.'
    });
  }

  const decoded = verifyToken(token);
  
  if (!decoded) {
    return res.status(401).json({
      message: 'The authentication token is invalid or has expired. Please log in again.'
    });
  }

  req.user = {
    username: decoded.username
  };

  next();
}

module.exports = {
  authenticateToken
};

