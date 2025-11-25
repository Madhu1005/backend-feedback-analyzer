# Zoho Cliq Extension - Sentiment Analysis Bot

AI-powered sentiment analysis bot for Zoho Cliq that detects employee emotions, stress levels, and provides empathetic response suggestions in real-time.

## 🚀 Quick Start

### Prerequisites
- Node.js >= 16.0.0
- npm >= 8.0.0
- Deployed FastAPI backend (already done on Railway)
- Zoho Cliq workspace with admin access

### Installation

1. **Install dependencies:**
```bash
cd cliq-extension
npm install
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env and fill in:
# - BACKEND_API_URL (your Railway backend URL)
# - ZOHO_VERIFICATION_TOKEN (from Zoho after extension registration)
```

3. **Validate setup:**
```bash
npm run validate
```

4. **Start the server:**
```bash
# Development with auto-reload
npm run dev

# Production
npm start
```

Server will start on `http://localhost:3000` (or your configured PORT).

## 📁 Project Structure

```
cliq-extension/
├── manifest.json              # Zoho Cliq extension configuration
├── server.js                  # Main Express server & routes
├── package.json               # Dependencies & scripts
├── .env.example               # Environment template
├── bot/
│   └── webhook_handler.js     # Bot message processing logic
├── commands/
│   └── team_mood.js           # /team-mood slash command
├── utils/
│   └── api_client.js          # Backend API communication utility
└── widgets/
    └── dashboard/             # (Future) Dashboard widget
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BACKEND_API_URL` | ✅ Yes | FastAPI backend URL (Railway) |
| `ZOHO_VERIFICATION_TOKEN` | ✅ Yes | Zoho webhook security token |
| `PORT` | ❌ No | Server port (default: 3000) |
| `STRESS_THRESHOLD` | ❌ No | High stress alert threshold (default: 7) |
| `ADMIN_ALERT_CHANNEL` | ❌ No | Channel ID for admin alerts |

### Deploying the Webhook Server

You need to deploy this server to a publicly accessible URL so Zoho can send webhooks.

**Option 1: Railway (Recommended)**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Deploy
railway up
```

**Option 2: Heroku**
```bash
heroku create your-app-name
git push heroku main
```

**Option 3: Any VPS**
- Use PM2 for process management
- Setup nginx reverse proxy
- Configure SSL certificate

## 📝 Registering the Extension in Zoho Cliq

1. **Go to Zoho Cliq → Settings → Extensions → Create**

2. **Upload `manifest.json`** (update webhook URLs first!)

3. **Replace placeholders in manifest.json:**
```json
"webhookUrl": "https://your-deployed-server.railway.app/bot/webhook"
```

4. **Copy the Verification Token** provided by Zoho and add to `.env`:
```env
ZOHO_VERIFICATION_TOKEN=abc123xyz789
```

5. **Install the extension** to your workspace

6. **Test the bot** by sending a message in any channel

## 🧪 Testing

### Manual Testing with cURL

**Test webhook endpoint:**
```bash
curl -X POST http://localhost:3000/bot/webhook \
  -H "Content-Type: application/json" \
  -H "x-zoho-verification-token: your_token" \
  -d '{
    "type": "message",
    "message": {
      "text": "I am feeling overwhelmed with work"
    },
    "user": {
      "id": "test_user_123",
      "is_bot": false
    },
    "channel": {
      "id": "test_channel_456"
    }
  }'
```

**Test /team-mood command:**
```bash
curl -X POST http://localhost:3000/commands/team-mood \
  -H "Content-Type: application/json" \
  -d '{
    "user": {"id": "test_user"},
    "channel": {"id": "test_channel"}
  }'
```

**Test health check:**
```bash
curl http://localhost:3000/health
```

## 🤖 Bot Features

### Message Analysis
- **Automatic sentiment detection** on all channel messages
- **Rich card responses** with:
  - Sentiment (positive/neutral/negative)
  - Emotion (happy, stressed, anxious, etc.)
  - Stress score (0-10 visual bar)
  - Category (workload, communication, etc.)
  - AI-suggested empathetic reply
  - Interactive buttons (Send Reply, Flag Conversation)

### Slash Commands
- **`/team-mood`** - Display team sentiment analytics:
  - Sentiment distribution (positive/neutral/negative %)
  - Average stress score
  - Top issues detected
  - Trend indicator (improving/declining/stable)

### Message Actions (Right-click menu)
- **Analyze Sentiment** - Get instant analysis for any message
- **Suggest Reply** - Generate empathetic response suggestion

### Admin Alerts
- Automatic notifications to admin channel when stress >= threshold
- Configurable threshold (default: 7/10)

## 🔒 Security

- ✅ Webhook request verification using Zoho token
- ✅ No hardcoded secrets (environment variables)
- ✅ Request timeout protection (10s default)
- ✅ Error handling with retry logic
- ✅ CORS configuration for Zoho domains

## 📊 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/bot/webhook` | Bot message handler |
| `POST` | `/commands/team-mood` | Slash command handler |
| `POST` | `/actions/analyze` | Message action: analyze |
| `POST` | `/actions/suggest-reply` | Message action: suggest reply |
| `GET` | `/widgets/dashboard` | Widget dashboard |
| `GET` | `/health` | Health check |
| `GET` | `/` | Server info |

## 🐛 Debugging

**Enable verbose logging:**
```bash
NODE_ENV=development npm run dev
```

**Check backend connectivity:**
```bash
curl http://localhost:3000/health
```

**Common issues:**

1. **"Backend not responding"**
   - Verify `BACKEND_API_URL` is correct
   - Check Railway backend is running
   - Test backend `/health` endpoint directly

2. **"Unauthorized webhook request"**
   - Verify `ZOHO_VERIFICATION_TOKEN` matches Zoho
   - Check header: `x-zoho-verification-token`

3. **"Analysis failed"**
   - Check backend logs on Railway
   - Verify API endpoint `/analyze` is working
   - Test with curl directly to backend

## 🚀 Deployment Checklist

- [ ] Backend deployed and healthy on Railway
- [ ] Cliq extension server deployed (Railway/Heroku/VPS)
- [ ] `.env` configured with all required variables
- [ ] `manifest.json` updated with production URLs
- [ ] Extension registered in Zoho Cliq
- [ ] Verification token configured
- [ ] Tested bot responds to messages
- [ ] Tested `/team-mood` command
- [ ] Tested message actions (right-click)
- [ ] Admin alerts configured (optional)
- [ ] SSL/HTTPS enabled on webhook server

## 📚 Next Steps

1. **Implement Dashboard Widget** - Visual charts and trends
2. **Add OAuth Integration** - Direct Cliq API access for admin alerts
3. **Enhance Analytics** - Historical data, team comparisons
4. **Add More Commands** - `/stress-report`, `/emotion-trends`, etc.
5. **Automated Tests** - Unit and integration tests

## 🤝 Support

For issues or questions:
- Check backend logs on Railway
- Check extension server logs
- Review Zoho Cliq extension documentation
- Test endpoints with curl/Postman

---

**Built with ❤️ for employee wellness**
