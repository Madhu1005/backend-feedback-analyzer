/**
 * API Client Utility for Backend Communication
 * 
 * Handles all communication with the FastAPI backend.
 * Includes retry logic, error handling, and response validation.
 * 
 * Environment Variables Required:
 * - BACKEND_API_URL: Base URL of the FastAPI backend (from Zoho settings or .env)
 * - API_TIMEOUT: Request timeout in ms (default: 10000)
 */

const fetch = require('node-fetch');

class APIClient {
  constructor(baseURL = null) {
    this.baseURL = baseURL || process.env.BACKEND_API_URL;
    this.timeout = parseInt(process.env.API_TIMEOUT || '10000');
    this.maxRetries = 3;
    this.retryDelay = 1000; // 1 second
    
    // Circuit breaker state
    this.circuitBreakerFailures = 0;
    this.circuitBreakerThreshold = 5;
    this.circuitBreakerOpen = false;
    this.circuitBreakerResetTime = null;
    this.circuitBreakerTimeout = 30000; // 30s
  }

  /**
   * Check circuit breaker state
   * @private
   */
  _checkCircuitBreaker() {
    if (!this.circuitBreakerOpen) {
      return true;
    }

    // Check if timeout elapsed, reset if so
    if (Date.now() >= this.circuitBreakerResetTime) {
      console.log('[API] Circuit breaker reset - attempting request');
      this.circuitBreakerOpen = false;
      this.circuitBreakerFailures = 0;
      return true;
    }

    throw new Error('Circuit breaker is OPEN - backend unavailable');
  }

  /**
   * Record circuit breaker failure
   * @private
   */
  _recordFailure() {
    this.circuitBreakerFailures++;
    
    if (this.circuitBreakerFailures >= this.circuitBreakerThreshold) {
      this.circuitBreakerOpen = true;
      this.circuitBreakerResetTime = Date.now() + this.circuitBreakerTimeout;
      console.error(`[API] Circuit breaker OPEN after ${this.circuitBreakerFailures} failures`);
    }
  }

  /**
   * Reset circuit breaker on success
   * @private
   */
  _recordSuccess() {
    if (this.circuitBreakerFailures > 0) {
      this.circuitBreakerFailures = 0;
      console.log('[API] Circuit breaker failures reset');
    }
  }

  /**
   * Make HTTP request with retry logic
   * @private
   */
  async _makeRequest(url, options, retryCount = 0) {
    // Check circuit breaker
    this._checkCircuitBreaker();

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        this._recordFailure();
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      this._recordSuccess();
      return result;
    } catch (error) {
      clearTimeout(timeoutId);
      this._recordFailure();

      // Only retry GET requests (POST requests can cause duplicates)
      const isGetRequest = !options.method || options.method === 'GET';
      const shouldRetry = isGetRequest && retryCount < this.maxRetries && this._shouldRetry(error);

      if (shouldRetry) {
        console.warn(`Request failed, retrying (${retryCount + 1}/${this.maxRetries})...`, error.message);
        await this._sleep(this.retryDelay * (retryCount + 1));
        return this._makeRequest(url, options, retryCount + 1);
      }

      throw error;
    }
  }

  /**
   * Determine if request should be retried
   * @private
   */
  _shouldRetry(error) {
    // Retry on network errors, timeouts, or 5xx server errors
    return (
      error.name === 'AbortError' ||
      error.message.includes('ECONNREFUSED') ||
      error.message.includes('ETIMEDOUT') ||
      error.message.includes('HTTP 5')
    );
  }

  /**
   * Sleep utility for retry delays
   * @private
   */
  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Analyze message sentiment and emotion
   * 
   * @param {Object} payload - Analysis request
   * @param {string} payload.message - The message text to analyze
   * @param {string} [payload.user_id] - Optional user ID
   * @param {string} [payload.channel_id] - Optional channel ID
   * @returns {Promise<Object>} Analysis result with sentiment, emotion, stress_score, etc.
   * 
   * @example
   * const result = await apiClient.analyzeMessage({
   *   message: "I'm feeling overwhelmed with work",
   *   user_id: "user123",
   *   channel_id: "channel456"
   * });
   * // Returns: { sentiment, emotion, stress_score, category, suggested_reply, confidence, meta }
   */
  async analyzeMessage(payload) {
    const url = `${this.baseURL}/analyze`;
    
    console.log(`[API] Analyzing message: "${payload.message.substring(0, 50)}..."`);

    try {
      const result = await this._makeRequest(url, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      console.log(`[API] Analysis complete - Sentiment: ${result.sentiment}, Emotion: ${result.emotion}, Stress: ${result.stress_score}`);
      
      return result;
    } catch (error) {
      console.error('[API] Analysis failed:', error.message);
      throw new Error(`Backend analysis failed: ${error.message}`);
    }
  }

  /**
   * Get today's team statistics
   * 
   * @param {string} [channelId] - Optional channel ID to filter stats
   * @returns {Promise<Object>} Today's mood statistics
   * 
   * @example
   * const stats = await apiClient.getTodayStats('channel123');
   * // Returns: { positive_pct, neutral_pct, negative_pct, avg_stress, top_issues, trend }
   */
  async getTodayStats(channelId = null) {
    let url = `${this.baseURL}/stats/today`;
    if (channelId) {
      url += `?channel_id=${encodeURIComponent(channelId)}`;
    }

    console.log(`[API] Fetching today's stats${channelId ? ` for channel ${channelId}` : ''}`);

    try {
      const result = await this._makeRequest(url, {
        method: 'GET',
      });

      console.log('[API] Stats retrieved successfully');
      return result;
    } catch (error) {
      console.error('[API] Stats fetch failed:', error.message);
      throw new Error(`Failed to fetch stats: ${error.message}`);
    }
  }

  /**
   * Get historical trends
   * 
   * @param {number} [days=7] - Number of days to fetch
   * @param {string} [channelId] - Optional channel ID filter
   * @returns {Promise<Object>} Historical trend data
   */
  async getTrends(days = 7, channelId = null) {
    let url = `${this.baseURL}/stats/trends?days=${days}`;
    if (channelId) {
      url += `&channel_id=${encodeURIComponent(channelId)}`;
    }

    console.log(`[API] Fetching ${days}-day trends${channelId ? ` for channel ${channelId}` : ''}`);

    try {
      const result = await this._makeRequest(url, {
        method: 'GET',
      });

      console.log('[API] Trends retrieved successfully');
      return result;
    } catch (error) {
      console.error('[API] Trends fetch failed:', error.message);
      throw new Error(`Failed to fetch trends: ${error.message}`);
    }
  }

  /**
   * Health check - verify backend is reachable
   * 
   * @returns {Promise<boolean>} True if backend is healthy
   */
  async healthCheck() {
    const url = `${this.baseURL}/health`;

    try {
      const result = await this._makeRequest(url, {
        method: 'GET',
      });

      return result.status === 'healthy';
    } catch (error) {
      console.error('[API] Health check failed:', error.message);
      return false;
    }
  }

  /**
   * Validate configuration
   * Checks if API URL is set and backend is reachable
   */
  async validateConfig() {
    if (!this.baseURL) {
      throw new Error('BACKEND_API_URL is not configured. Please set it in extension settings.');
    }

    const isHealthy = await this.healthCheck();
    if (!isHealthy) {
      throw new Error(`Backend at ${this.baseURL} is not responding. Please check the URL and backend status.`);
    }

    console.log(`[API] Configuration validated - Backend is healthy at ${this.baseURL}`);
    return true;
  }
}

module.exports = APIClient;
