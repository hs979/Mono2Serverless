require('dotenv').config();

const express = require('express');
const cors = require('cors');
const authRoutes = require('./routes/auth');
const todoRoutes = require('./routes/todo');

const app = express();
const PORT = process.env.PORT || 8080;

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

app.use('/auth', authRoutes);
app.use('/api', todoRoutes);

app.get('/', (req, res) => {
  res.json({
    message: 'Todo application backend service is running',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

app.use((req, res) => {
  res.status(404).json({ message: 'Resource not found' });
});

app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).json({
    message: 'Internal server error',
    error: process.env.NODE_ENV === 'development' ? err.message : undefined
  });
});

app.listen(PORT, () => {
  console.log(`========================================`);
  console.log(`Todo application backend service started`);
  console.log(`Running at: http://localhost:${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`========================================`);
});

process.on('SIGTERM', () => {
  console.log('Received SIGTERM signal, shutting down server...');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('Received SIGINT signal, shutting down server...');
  process.exit(0);
});

