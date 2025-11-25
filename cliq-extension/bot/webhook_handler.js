/**
 * Bot Webhook Handler
 * 
 * Handles all incoming messages from Zoho Cliq channels and conversations.
 * Analyzes sentiment and responds with rich cards containing insights.
 * 
 * Flow:
 * 1. Receive webhook event from Zoho
 * 2. Verify request authenticity (security token)
 * 3. Extract message text
 * 4. Call backend /analyze endpoint
 * 5. Build rich card response
 * 6. Send back to Zoho
 * 
 * Environment Variables:
 * - ZOHO_VERIFICATION_TOKEN: Token from Zoho for request verification
 * - BACKEND_API_URL: FastAPI backend URL
 * - STRESS_THRESHOLD: Alert threshold for high stress (default: 7)
 */

const APIClient = require('../utils/api_client');

class BotWebhookHandler {
  constructor() {
    this.apiClient = new APIClient();
    this.verificationToken = process.env.ZOHO_VERIFICATION_TOKEN;
    this.stressThreshold = parseInt(process.env.STRESS_THRESHOLD || '7');
  }

  /**
   * Main webhook handler
   * Express middleware: (req, res) => {}
   */
  async handleWebhook(req, res) {
    try {
      // Security: Verify request came from Zoho
      if (!this._verifyRequest(req)) {
        console.warn('[Bot] Unauthorized webhook request');
        return res.status(401).json({ error: 'Unauthorized' });
      }

      const event = req.body;
      console.log(`[Bot] Received event type: ${event.type}`);

      // Handle different event types
      let response;
      switch (event.type) {
        case 'message':
          response = await this._handleMessage(event);
          break;
        case 'bot_mention':
          response = await this._handleMention(event);
          break;
        case 'participant_joined':
          response = await this._handleParticipantJoined(event);
          break;
        default:
          console.log(`[Bot] Ignoring event type: ${event.type}`);
          return res.status(200).json({ text: 'Event received' });
      }

      return res.status(200).json(response);
    } catch (error) {
      console.error('[Bot] Webhook error:', error);
      return res.status(500).json({
        text: '⚠️ Analysis temporarily unavailable. Please try again.',
      });
    }
  }

  /**
   * Verify webhook request authenticity
   * Uses timing-safe comparison to prevent timing attacks
   * @private
   */
  _verifyRequest(req) {
    if (!this.verificationToken) {
      console.warn('[Bot] No verification token configured - accepting all requests (INSECURE)');
      return true;
    }

    // Prefer header over body token
    const token = req.headers['x-zoho-verification-token'];
    
    if (!token) {
      return false;
    }

    // Timing-safe comparison
    const crypto = require('crypto');
    const expected = Buffer.from(this.verificationToken);
    const actual = Buffer.from(token);
    
    if (expected.length !== actual.length) {
      return false;
    }
    
    return crypto.timingSafeEqual(expected, actual);
  }

  /**
   * Handle regular message event
   * @private
   */
  async _handleMessage(event) {
    // Validate event structure
    if (!event || typeof event !== 'object') {
      console.warn('[Bot] Invalid event object');
      return { text: '' };
    }

    const message = event.message?.text || '';
    const userId = event.user?.id;
    const channelId = event.channel?.id;

    // Skip empty messages or bot's own messages
    if (!message.trim() || event.user?.is_bot) {
      return { text: '' };
    }

    // Validate message length (prevent abuse)
    if (message.length > 5000) {
      console.warn('[Bot] Message too long, truncating');
      return { text: '⚠️ Message too long for analysis (max 5000 chars)' };
    }

    console.log(`[Bot] Analyzing message from user ${userId}: "${message.substring(0, 50)}..."`);

    // Call backend for analysis
    const analysis = await this.apiClient.analyzeMessage({
      message,
      user_id: userId,
      channel_id: channelId,
    });

    // Build response card
    const card = this._buildAnalysisCard(analysis, message);

    // Check if stress is high and needs admin alert
    if (analysis.stress_score >= this.stressThreshold) {
      await this._sendAdminAlert(analysis, userId, channelId);
    }

    return card;
  }

  /**
   * Handle bot mention (@emo-bot)
   * @private
   */
  async _handleMention(event) {
    const message = event.message?.text || '';
    const command = message.replace(/@emo-bot/i, '').trim().toLowerCase();

    if (command.includes('help')) {
      return this._buildHelpCard();
    }

    if (command.includes('status')) {
      const isHealthy = await this.apiClient.healthCheck();
      return {
        text: isHealthy ? '✅ Backend is healthy and ready!' : '⚠️ Backend is not responding',
      };
    }

    // Default: analyze the message
    return this._handleMessage(event);
  }

  /**
   * Handle new participant joining
   * @private
   */
  async _handleParticipantJoined(event) {
    const userName = event.user?.name || 'New member';
    return {
      text: `👋 Welcome ${userName}! I'm Emo-Bot, your sentiment analysis assistant. I can help detect emotions and provide empathetic responses. Type @emo-bot help to learn more!`,
    };
  }

  /**
   * Build rich card for analysis results
   * @private
   */
  _buildAnalysisCard(analysis, originalMessage) {
    // Sentiment emoji mapping
    const sentimentEmoji = {
      positive: '😊',
      neutral: '😐',
      negative: '😔',
    };

    // Emotion emoji mapping
    const emotionEmoji = {
      happy: '😄',
      sad: '😢',
      angry: '😠',
      stressed: '😰',
      anxious: '😟',
      frustrated: '😤',
      excited: '🤩',
      calm: '😌',
    };

    // Stress level color
    const stressColor = analysis.stress_score >= 7 ? '#FF5252' : analysis.stress_score >= 4 ? '#FFC107' : '#4CAF50';

    return {
      text: 'Analysis Complete',
      card: {
        title: `${sentimentEmoji[analysis.sentiment] || '🤔'} Sentiment Analysis`,
        theme: analysis.sentiment === 'negative' ? 'modern-inline' : 'prompt',
        sections: [
          {
            id: 1,
            elements: [
              {
                type: 'text',
                text: `**Sentiment:** ${analysis.sentiment.charAt(0).toUpperCase() + analysis.sentiment.slice(1)}`,
              },
              {
                type: 'text',
                text: `**Emotion:** ${emotionEmoji[analysis.emotion] || '🤔'} ${analysis.emotion}`,
              },
              {
                type: 'text',
                text: `**Stress Level:** ${this._buildStressBar(analysis.stress_score)}`,
              },
              {
                type: 'text',
                text: `**Category:** ${analysis.category}`,
              },
              {
                type: 'text',
                text: `**Confidence:** ${Math.round(analysis.confidence * 100)}%`,
              },
            ],
          },
          {
            id: 2,
            elements: [
              {
                type: 'divider',
              },
              {
                type: 'text',
                text: `**💡 Suggested Reply:**\n_"${analysis.suggested_reply}"_`,
              },
            ],
          },
        ],
        buttons: [
          {
            label: '📤 Send Reply',
            type: 'invoke.function',
            name: 'sendSuggestedReply',
            id: 'send_reply_btn',
            data: {
              reply: analysis.suggested_reply,
              channel_id: event.channel?.id,
            },
          },
          {
            label: '🚩 Flag for Review',
            type: 'invoke.function',
            name: 'flagConversation',
            id: 'flag_btn',
            data: {
              stress_score: analysis.stress_score,
              sentiment: analysis.sentiment,
              message: originalMessage.substring(0, 100),
            },
          },
        ],
      },
    };
  }

  /**
   * Build visual stress bar (monospace-friendly)
   * @private
   */
  _buildStressBar(score) {
    const filled = Math.round(score);
    const bar = '█'.repeat(filled) + '░'.repeat(10 - filled);
    return `[${bar}] ${score}/10`;
  }

  /**
   * Build help card
   * @private
   */
  _buildHelpCard() {
    return {
      text: 'Emo-Bot Help',
      card: {
        title: '🤖 Emo-Bot - Sentiment Analysis Assistant',
        theme: 'modern-inline',
        sections: [
          {
            id: 1,
            elements: [
              {
                type: 'text',
                text: '**What I Do:**\nI analyze messages in real-time to detect emotions, sentiment, and stress levels. I provide empathetic response suggestions to help improve team communication.',
              },
              {
                type: 'divider',
              },
              {
                type: 'text',
                text: '**Commands:**\n• `/team-mood` - View team sentiment analytics\n• `@emo-bot help` - Show this help\n• `@emo-bot status` - Check backend status',
              },
              {
                type: 'divider',
              },
              {
                type: 'text',
                text: '**Message Actions:**\nRight-click any message → "Analyze Sentiment" to get instant insights',
              },
            ],
          },
        ],
      },
    };
  }

  /**
   * Send alert to admin channel for high-stress messages
   * @private
   */
  async _sendAdminAlert(analysis, userId, channelId) {
    const adminChannel = process.env.ADMIN_ALERT_CHANNEL;
    if (!adminChannel) {
      return; // No admin channel configured
    }

    console.log(`[Bot] 🚨 High stress detected (${analysis.stress_score}/10) - Alerting admins`);

    // TODO: Implement Zoho Cliq API call to send message to admin channel
    // This would require Zoho OAuth tokens and Cliq API client
    // For now, just log the alert
  }
}

// Express route handler wrapper
function createWebhookHandler() {
  const handler = new BotWebhookHandler();
  return (req, res) => handler.handleWebhook(req, res);
}

module.exports = { BotWebhookHandler, createWebhookHandler };
