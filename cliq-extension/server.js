/**
 * Main Express Server for Zoho Cliq Extension
 * 
 * Routes:
 * - POST /bot/webhook - Bot message handler
 * - POST /commands/team-mood - Slash command handler
 * - POST /actions/analyze - Message action: analyze sentiment
 * - POST /actions/suggest-reply - Message action: suggest reply
 * - GET /widgets/dashboard - Widget dashboard (serves HTML)
 * - GET /health - Health check endpoint
 * 
 * Environment Variables:
 * - PORT: Server port (default: 3000)
 * - BACKEND_API_URL: FastAPI backend URL
 * - ZOHO_VERIFICATION_TOKEN: Zoho webhook verification token
 * - STRESS_THRESHOLD: High stress alert threshold (default: 7)
 * - ADMIN_ALERT_CHANNEL: Channel ID for admin alerts
 */

const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
require('dotenv').config();

const { createWebhookHandler } = require('./bot/webhook_handler');
const { createCommandHandler } = require('./commands/team_mood');
const APIClient = require('./utils/api_client');

// Initialize Express app
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
// CORS only for widget endpoints, Zoho domains only
app.use('/widgets', cors({
  origin: [
    'https://cliq.zoho.com',
    'https://cliq.zoho.eu',
    'https://cliq.zoho.in'
  ],
  credentials: true
}));

// Body parsing with size limits (prevent DoS)
app.use(bodyParser.json({ limit: '200kb' }));
app.use(bodyParser.urlencoded({ extended: true, limit: '200kb' }));

// Request logging middleware
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

// Initialize API client
const apiClient = new APIClient();

// ==================== ROUTES ====================

/**
 * Bot webhook endpoint
 * Handles all incoming messages from Zoho Cliq
 */
app.post('/bot/webhook', createWebhookHandler());

/**
 * Slash command: /team-mood
 * Returns team sentiment statistics
 */
app.post('/commands/team-mood', createCommandHandler());

/**
 * Message action: Analyze Sentiment
 * Right-click context menu on any message
 */
app.post('/actions/analyze', async (req, res) => {
  try {
    const { message, user, channel } = req.body;
    
    const analysis = await apiClient.analyzeMessage({
      message: message?.text || '',
      user_id: user?.id,
      channel_id: channel?.id,
    });

    res.json({
      text: 'Analysis Complete',
      card: {
        title: '🔍 Sentiment Analysis',
        sections: [
          {
            elements: [
              { type: 'text', text: `**Sentiment:** ${analysis.sentiment}` },
              { type: 'text', text: `**Emotion:** ${analysis.emotion}` },
              { type: 'text', text: `**Stress:** ${analysis.stress_score}/10` },
              { type: 'text', text: `**Category:** ${analysis.category}` },
            ],
          },
        ],
      },
    });
  } catch (error) {
    console.error('[Action] Analyze error:', error);
    res.json({ text: '⚠️ Analysis failed. Please try again.' });
  }
});

/**
 * Message action: Suggest Reply
 * Provides AI-generated empathetic response
 */
app.post('/actions/suggest-reply', async (req, res) => {
  try {
    const { message } = req.body;
    
    const analysis = await apiClient.analyzeMessage({
      message: message?.text || '',
    });

    res.json({
      text: '💡 Suggested Reply',
      card: {
        title: 'Suggested Response',
        sections: [
          {
            elements: [
              { type: 'text', text: `_"${analysis.suggested_reply}"_` },
            ],
          },
        ],
        buttons: [
          {
            label: '📤 Send Reply',
            type: 'invoke.function',
            name: 'sendReply',
            data: { reply: analysis.suggested_reply },
          },
        ],
      },
    });
  } catch (error) {
    console.error('[Action] Suggest reply error:', error);
    res.json({ text: '⚠️ Unable to generate suggestion. Please try again.' });
  }
});

/**
 * Widget: Dashboard
 * Serves the team sentiment dashboard
 */
app.get('/widgets/dashboard', (req, res) => {
  // TODO: Serve actual dashboard HTML with charts
  res.send(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Team Sentiment Dashboard</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
        .dashboard { background: white; padding: 20px; border-radius: 8px; }
        h1 { color: #333; }
      </style>
    </head>
    <body>
      <div class="dashboard">
        <h1>📊 Team Sentiment Dashboard</h1>
        <p>Dashboard implementation coming soon...</p>
        <p>This will display:</p>
        <ul>
          <li>Real-time sentiment charts</li>
          <li>Stress level trends</li>
          <li>Top issues breakdown</li>
          <li>Individual team member insights</li>
        </ul>
      </div>
    </body>
    </html>
  `);
});

/**
 * Health check endpoint
 * Verifies server and backend connectivity
 */
app.get('/health', async (req, res) => {
  try {
    const backendHealthy = await apiClient.healthCheck();
    res.json({
      status: 'healthy',
      server: 'ok',
      backend: backendHealthy ? 'ok' : 'down',
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    res.status(503).json({
      status: 'unhealthy',
      error: error.message,
    });
  }
});

/**
 * Root endpoint
 */
app.get('/', (req, res) => {
  res.json({
    name: 'Zoho Cliq Extension - Sentiment Analysis Bot',
    version: '1.0.0',
    status: 'running',
    endpoints: {
      webhook: '/bot/webhook',
      command: '/commands/team-mood',
      actions: ['/actions/analyze', '/actions/suggest-reply'],
      widget: '/widgets/dashboard',
      health: '/health',
    },
  });
});

// ==================== ERROR HANDLING ====================

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Endpoint not found' });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('[Server] Unhandled error:', err);
  res.status(500).json({
    error: 'Internal server error',
    message: process.env.NODE_ENV === 'development' ? err.message : undefined,
  });
});

// ==================== SERVER START ====================

// Validate configuration on startup
async function validateSetup() {
  console.log('🔍 Validating configuration...');
  
  if (!process.env.BACKEND_API_URL) {
    console.error('❌ BACKEND_API_URL is not set!');
    process.exit(1);
  }

  if (!process.env.ZOHO_VERIFICATION_TOKEN) {
    console.warn('⚠️  ZOHO_VERIFICATION_TOKEN is not set - webhook security disabled!');
  }

  try {
    await apiClient.validateConfig();
    console.log('✅ Backend connection verified');
  } catch (error) {
    console.error('❌ Backend validation failed:', error.message);
    console.warn('⚠️  Starting server anyway, but functionality will be limited');
  }
}

// Start server
if (require.main === module) {
  validateSetup().then(() => {
    app.listen(PORT, () => {
      console.log('');
      console.log('🚀 ============================================');
      console.log(`🤖 Zoho Cliq Extension Server Running`);
      console.log(`📡 Port: ${PORT}`);
      console.log(`🔗 Backend: ${process.env.BACKEND_API_URL}`);
      console.log('🛠️  Endpoints:');
      console.log(`   - Webhook:  POST http://localhost:${PORT}/bot/webhook`);
      console.log(`   - Command:  POST http://localhost:${PORT}/commands/team-mood`);
      console.log(`   - Health:   GET  http://localhost:${PORT}/health`);
      console.log('============================================');
      console.log('');
    });
  });
}

module.exports = app;
