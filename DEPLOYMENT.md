# Deployment Guide - PharmaStock Web Application

## Quick Start

1. **Install dependencies:**
   ```bash
   cd web_app
   pip install -r requirements.txt
   ```

2. **Set up Google Drive API:**
   - Download OAuth2 credentials from Google Cloud Console
   - Save as `google_credentials.json` in `web_app/` directory
   - Run app once to authorize (will prompt for code)

3. **Configure settings:**
   - Copy `.env.example` to `.env`
   - Update `SECRET_KEY` and other settings

4. **Run the application:**
   ```bash
   python -m app.main
   ```
   Or:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

5. **Access:** `http://localhost:8000`

## Google Drive API Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "PharmaStock"
3. Enable **Google Drive API**

### Step 2: Create OAuth2 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Desktop app**
4. Name: "PharmaStock Desktop Client"
5. Click **Create**
6. Download JSON file
7. Save as `google_credentials.json` in `web_app/` directory

### Step 3: Authorize Application

1. Run the app: `python -m app.main`
2. First run will show authorization URL
3. Visit URL in browser
4. Sign in with `controleddrugsalesdaimamerudda@gmail.com`
5. Copy authorization code
6. Paste code when prompted
7. Token saved to `google_token.json`

## Adding Licensed Emails

### Method 1: Admin Panel (Web UI)

1. Login as admin (email from `GOOGLE_DRIVE_EMAIL`)
2. Go to **Admin** page
3. Enter email address
4. Click **Add License**

### Method 2: Edit license_db.json

```json
{
  "licensed_emails": [
    "user1@example.com",
    "user2@example.com"
  ],
  "admin_emails": [
    "controleddrugsalesdaimamerudda@gmail.com"
  ]
}
```

## Production Deployment

### Option 1: Google Cloud Run

```bash
# Build and deploy
gcloud run deploy pharmastock-web \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars SECRET_KEY=your-secret-key
```

### Option 2: Self-Hosted with Gunicorn

```bash
gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Option 3: Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t pharmastock-web .
docker run -p 8000:8000 \
  -v $(pwd)/google_credentials.json:/app/google_credentials.json \
  -v $(pwd)/google_token.json:/app/google_token.json \
  -v $(pwd)/license_db.json:/app/license_db.json \
  pharmastock-web
```

## Environment Variables

Create `.env` file:

```env
SECRET_KEY=your-very-secret-key-here
GOOGLE_DRIVE_EMAIL=controleddrugsalesdaimamerudda@gmail.com
AUTO_REFRESH_INTERVAL_MINUTES=60
AUTO_REFRESH_ENABLED=true
```

## Troubleshooting

### "Google credentials file not found"
- Download OAuth2 credentials from Google Cloud Console
- Save as `google_credentials.json` in `web_app/` directory

### "Email not licensed"
- Add email to `license_db.json` or use admin panel
- Admin email is automatically licensed

### "Database not found"
- First refresh will create database
- Or manually sync from Drive using admin panel

### Refresh not working
- Check credentials are saved in Settings
- Verify API URLs are correct
- Check logs for detailed errors

## Security Notes

- Change `SECRET_KEY` in production
- Use HTTPS in production
- Restrict CORS origins appropriately
- Keep `google_credentials.json` and `google_token.json` secure
- Don't commit credentials to version control

