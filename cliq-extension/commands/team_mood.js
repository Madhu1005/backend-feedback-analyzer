/**
 * /team-mood Slash Command Handler
 * 
 * Displays today's team sentiment statistics in a rich card format.
 * Shows positive/neutral/negative percentages, average stress, top issues, and trends.
 * 
 * Usage: /team-mood [channel_id]
 * 
 * Environment Variables:
 * - BACKEND_API_URL: FastAPI backend URL
 */

const APIClient = require('../utils/api_client');

class TeamMoodCommandHandler {
  constructor() {
    this.apiClient = new APIClient();
  }

  /**
   * Main command handler
   * Express middleware: (req, res) => {}
   */
  async handleCommand(req, res) {
    try {
      const { arguments: args, user, channel } = req.body;

      console.log(`[Command] /team-mood invoked by user ${user?.id} in channel ${channel?.id}`);

      // Extract optional channel ID from arguments
      const targetChannelId = args?.channel_id || channel?.id;

      // Fetch stats from backend
      const stats = await this.apiClient.getTodayStats(targetChannelId);

      // Build response card
      const card = this._buildStatsCard(stats, targetChannelId);

      return res.status(200).json(card);
    } catch (error) {
      console.error('[Command] /team-mood error:', error);
      return res.status(200).json({
        text: '⚠️ Unable to fetch team mood data. Please try again or contact support.',
      });
    }
  }

  /**
   * Sanitize text to prevent injection
   * @private
   */
  _sanitize(text) {
    if (typeof text !== 'string') return '';
    return text
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;')
      .substring(0, 500); // Limit length
  }

  /**
   * Validate and normalize numeric value
   * @private
   */
  _validateNumber(value, defaultValue = 0, min = 0, max = 100) {
    const num = parseFloat(value);
    if (isNaN(num)) return defaultValue;
    return Math.max(min, Math.min(max, num));
  }

  /**
   * Build rich stats card
   * @private
   */
  _buildStatsCard(stats, channelId) {
    // Validate input
    if (!stats || typeof stats !== 'object') {
      throw new Error('Invalid stats object received from backend');
    }

    const {
      positive_pct = 0,
      neutral_pct = 0,
      negative_pct = 0,
      avg_stress = 0,
      top_issues = [],
      trend = 'stable',
      total_messages = 0,
    } = stats;

    // Validate percentages
    const posPct = this._validateNumber(positive_pct, 0, 0, 100);
    const neuPct = this._validateNumber(neutral_pct, 0, 0, 100);
    const negPct = this._validateNumber(negative_pct, 0, 0, 100);
    const avgStress = this._validateNumber(avg_stress, 0, 0, 10);
    const totalMsg = Math.max(0, parseInt(total_messages) || 0);

    // Trend emoji
    const trendEmoji = {
      up: '📈 Improving',
      down: '📉 Declining',
      stable: '➡️ Stable',
    };

    // Overall mood emoji based on positive percentage
    const moodEmoji = positive_pct >= 60 ? '😊' : positive_pct >= 40 ? '😐' : '😔';

    return {
      text: 'Team Mood Report',
      card: {
        title: `${moodEmoji} Team Mood - Today's Report`,
        theme: 'modern-inline',
        sections: [
          {
            id: 1,
            title: '📊 Sentiment Distribution',
            elements: [
              {
                type: 'text',
                text: this._buildSentimentBars(posPct, neuPct, negPct),
              },
              {
                type: 'text',
                text: `**Total Messages Analyzed:** ${totalMsg}`,
              },
            ],
          },
          {
            id: 2,
            title: '🌡️ Stress Levels',
            elements: [
              {
                type: 'text',
                text: `**Average Stress Score:** ${avgStress.toFixed(1)}/10`,
              },
              {
                type: 'text',
                text: this._buildStressIndicator(avgStress),
              },
            ],
          },
          {
            id: 3,
            title: '🔍 Top Issues',
            elements: [
              {
                type: 'text',
                text: top_issues.length > 0 
                  ? this._formatTopIssues(top_issues)
                  : '_No significant issues detected today_ ✨',
              },
            ],
          },
          {
            id: 4,
            title: '📈 Trend',
            elements: [
              {
                type: 'text',
                text: `**Compared to Yesterday:** ${trendEmoji[trend] || '➡️ Stable'}`,
              },
            ],
          },
        ],
        buttons: [
          {
            label: '📊 View Dashboard',
            type: 'open.url',
            url: `${process.env.DASHBOARD_URL || '#'}?channel=${channelId}`,
          },
          {
            label: '🔄 Refresh',
            type: 'invoke.function',
            name: 'refreshMood',
            id: 'refresh_btn',
          },
        ],
      },
    };
  }

  /**
   * Build visual sentiment bars
   * @private
   */
  _buildSentimentBars(positive, neutral, negative) {
    const posBar = this._createBar(positive, '🟢');
    const neuBar = this._createBar(neutral, '🟡');
    const negBar = this._createBar(negative, '🔴');

    return `**😊 Positive:** ${positive.toFixed(1)}% ${posBar}\n**😐 Neutral:** ${neutral.toFixed(1)}% ${neuBar}\n**😔 Negative:** ${negative.toFixed(1)}% ${negBar}`;
  }

  /**
   * Create progress bar
   * @private
   */
  _createBar(percentage, emoji) {
    const filled = Math.round(percentage / 10);
    const empty = 10 - filled;
    return emoji.repeat(filled) + '⬜'.repeat(empty);
  }

  /**
   * Build stress indicator
   * @private
   */
  _buildStressIndicator(avgStress) {
    if (avgStress >= 7) {
      return '🔴 **HIGH** - Team may need support';
    } else if (avgStress >= 4) {
      return '🟡 **MODERATE** - Monitor closely';
    } else {
      return '🟢 **LOW** - Team is doing well';
    }
  }

  /**
   * Format top issues list
   * @private
   */
  _formatTopIssues(issues) {
    if (!Array.isArray(issues)) return '_No data available_';
    
    return issues
      .slice(0, 5) // Top 5 issues
      .filter(issue => issue && typeof issue === 'object')
      .map((issue, index) => {
        const category = this._sanitize(issue.category || 'Unknown');
        const count = Math.max(0, parseInt(issue.count) || 0);
        return `${index + 1}. **${category}** (${count} mentions)`;
      })
      .join('\n') || '_No issues detected_';
  }
}

// Express route handler wrapper
function createCommandHandler() {
  const handler = new TeamMoodCommandHandler();
  return (req, res) => handler.handleCommand(req, res);
}

module.exports = { TeamMoodCommandHandler, createCommandHandler };
