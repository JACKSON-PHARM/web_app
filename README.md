# PharmaStock Web Application

FastAPI-based web application for pharmaceutical inventory management with Google Drive integration.

## Features

- ✅ **Web-based** - Access from any browser, no installation needed
- ✅ **Google Drive Integration** - Database stored in Google Drive (10GB+ storage)
- ✅ **Email-based Licensing** - Only licensed emails can access
- ✅ **Automatic Refresh** - Scheduled data refresh at configurable intervals
- ✅ **Manual Refresh** - Users can trigger refresh with their credentials
- ✅ **Multi-user** - Shared database, everyone sees latest data
- ✅ **Commercial Control** - Admin manages licenses and access

## Setup Instructions

### 1. Install Dependencies

```bash
cd web_app
pip install -r requirements.txt
```

### 2. Google Drive API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Drive API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download credentials JSON file
6. Save as `google_credentials.json` in `web_app/` directory
7. Run the app once - it will prompt for authorization
8. Enter the authorization code when prompted

### 3. Configure Settings

Edit `app/config.py` or create `.env` file:

```env
GOOGLE_DRIVE_EMAIL=controleddrugsalesdaimamerudda@gmail.com
SECRET_KEY=your-secret-key-here
AUTO_REFRESH_INTERVAL_MINUTES=60
AUTO_REFRESH_ENABLED=true
```

### 4. Add Licensed Emails

The admin email (from `GOOGLE_DRIVE_EMAIL`) is automatically licensed.

To add more licensed emails, use the admin panel after starting the app, or edit `license_db.json`:

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

### 5. Run the Application

```bash
cd web_app
python -m app.main
```

Or use uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Access the Application

Open browser: `http://localhost:8000`

## First Time Setup

1. **Login** with your licensed email
2. **Configure Credentials** - Enter NILA/DAIMA credentials in Settings
3. **Trigger Refresh** - Click "Refresh All Data" to sync initial data
4. **View Dashboard** - See new arrivals and priority items

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with email
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/logout` - Logout

### Dashboard
- `GET /api/dashboard/new-arrivals` - Get new arrivals
- `GET /api/dashboard/priority-items` - Get priority items
- `GET /api/dashboard/branches` - Get branch list

### Data Refresh
- `POST /api/refresh/all` - Trigger manual refresh
- `GET /api/refresh/status` - Get refresh scheduler status
- `POST /api/refresh/trigger` - Trigger immediate refresh

### Credentials
- `POST /api/credentials/save` - Save company credentials
- `POST /api/credentials/test` - Test credentials
- `GET /api/credentials/status` - Get credentials status

### Admin
- `POST /api/admin/licenses/add` - Add licensed email
- `POST /api/admin/licenses/remove` - Remove licensed email
- `GET /api/admin/licenses/list` - List all licenses
- `GET /api/admin/drive/info` - Get Google Drive info
- `POST /api/admin/drive/sync` - Sync database from Drive

## Deployment

### Option 1: Google Cloud Run

```bash
gcloud run deploy pharmastock-web \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Option 2: Self-Hosted Server

```bash
# Using gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Or using uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Option 3: Docker

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Architecture

- **Frontend**: HTML/CSS/JavaScript (templates in `templates/`)
- **Backend**: FastAPI (Python)
- **Database**: SQLite (stored in Google Drive)
- **Authentication**: JWT tokens with email-based licensing
- **Refresh**: Scheduled background tasks + manual triggers

## Notes

- Database is automatically synced to/from Google Drive
- Users provide their own NILA/DAIMA credentials
- Admin can manage licenses via web interface
- Auto-refresh runs at configured intervals
- All users see the same updated data

