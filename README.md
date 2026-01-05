# Page Watcher

Automated web page monitoring with WhatsApp and Gmail notifications via GitHub Actions. Get notified when any web page changes based on keywords or CSS selectors.

## Features

- ✅ Monitors page every 2 hours (low GitHub Actions quota usage)
- ✅ Keyword-based detection with full page change tracking (minimal false positives)
- ✅ WhatsApp notifications via Twilio
- ✅ Gmail notifications via SMTP
- ✅ Automatic retry logic with exponential backoff
- ✅ Graceful error handling
- ✅ Manual trigger support for testing

## Setup Instructions

### 1. Fork/Clone this repository

### 2. Configure GitHub Secrets

Go to your repository's **Settings → Secrets and variables → Actions** and add the following secrets:

#### Required Secrets

- `WATCH_URL` - The URL to monitor
  ```
  https://example.com/your-page-to-monitor
  ```

- `WATCH_KEYWORDS` - Comma-separated keywords to detect (case-insensitive)
  ```
  register now,registration open,available,in stock
  ```

#### Gmail Notification (Optional but Recommended)

- `SMTP_HOST` - Your SMTP server (e.g., `smtp.gmail.com`)
- `SMTP_PORT` - SMTP port (usually `587` for TLS)
- `SMTP_USER` - Your email address
- `SMTP_PASS` - Your email password or app-specific password
  - For Gmail: [Create an App Password](https://support.google.com/accounts/answer/185833)
- `EMAIL_TO` - Recipient email address
- `EMAIL_FROM` - Sender email (can be same as `SMTP_USER`)

#### WhatsApp Notification via Twilio (Optional but Recommended)

1. Sign up for [Twilio](https://www.twilio.com/) (free trial available)
2. Enable WhatsApp in Twilio Console
3. Add these secrets:
   - `TWILIO_ACCOUNT_SID` - From Twilio Console
   - `TWILIO_AUTH_TOKEN` - From Twilio Console
   - `WHATSAPP_FROM` - Twilio WhatsApp number (format: `whatsapp:+14155238886`)
   - `WHATSAPP_TO` - Your WhatsApp number (format: `whatsapp:+1234567890`)

### 3. Test Your Setup

#### Option A: Manual Workflow Trigger

1. Go to **Actions** tab in your repository
2. Select "Page Watcher"
3. Click "Run workflow"
4. Check the logs to see if it runs successfully

#### Option B: Test Notifications

Add a secret `FORCE_NOTIFY=true` to trigger a test notification on the next run.

### 4. Enable Actions (if not already enabled)

Make sure GitHub Actions is enabled:
- Go to **Settings → Actions → General**
- Ensure "Allow all actions and reusable workflows" is selected

## How It Works

1. **First Run**: Establishes a baseline (hash of page content) - no notification sent
2. **Subsequent Runs**:
   - Fetches the page every 2 hours
   - Checks if monitored keywords appear or if page content changes
   - If changed, sends notifications via configured channels
   - Updates the baseline to avoid duplicate alerts

## Monitoring Schedule

- **Cron**: Every 2 hours (`0 */2 * * *`)
- **Checks per day**: 12
- **Checks per month**: ~360
- **GitHub Actions usage**: < 20 minutes/month (well within free tier)

## Detection Method

The script uses a **hybrid approach** for minimal false positives:

1. **Keyword monitoring**: Tracks specific keywords you define
2. **Full page hash**: Detects ANY content change, not just keyword changes
3. **Result**: You'll be notified when:
   - Target keywords appear or disappear
   - Any significant page content changes
   - The page structure or text is modified

## File Structure

```
.
├── .github/
│   └── workflows/
│       └── watch.yml          # GitHub Actions workflow
├── scripts/
│   └── watch_page.py          # Python monitoring script
├── state/
│   └── page_state.json        # Stores last known state
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Troubleshooting

### No notifications received

1. Check the Actions tab for workflow run logs
2. Verify all required secrets are set correctly
3. For Gmail: Ensure you're using an App Password, not your regular password
4. For WhatsApp: Complete Twilio sandbox setup and join the sandbox

### Workflow failing

- Check the error logs in the Actions tab
- Common issues:
  - Missing required secrets
  - Invalid credentials
  - Network timeout (script will retry automatically)

### Too many false positives

If you're getting notified for minor changes:
1. Use the `WATCH_SELECTOR` secret instead of keywords to target a specific HTML element
2. Example: `.registration-button` or `#register-link`

### Testing changes locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export WATCH_URL="https://example.com/your-page"
export WATCH_KEYWORDS="your,keywords,here"

# Run the script
python scripts/watch_page.py
```

## GitHub Actions Quota

**Free tier limits**: 2,000 minutes/month

**This setup uses**:
- ~1.5 minutes per run
- 12 runs per day
- ~18 minutes per day
- **~540 minutes per month** (well within limits)

If you need to reduce usage further, change the cron schedule in `.github/workflows/watch.yml`:
- Every 4 hours: `0 */4 * * *`
- Every 6 hours: `0 */6 * * *`

## Security Notes

- Never commit secrets to the repository
- Use GitHub Secrets for all sensitive data
- Secrets are encrypted and only accessible to Actions
- The workflow only has write access to the `state/` directory

## License

MIT License - Feel free to use and modify as needed.

## Support

For issues or questions:
1. Check the workflow logs in the Actions tab
2. Review this README
3. Open an issue in this repository
