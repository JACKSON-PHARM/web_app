# 📤 Push Your Code to GitHub

Based on your GitHub repository: `JACKSON-PHARM/pharma-stock-app`

## Step-by-Step Instructions

### Option 1: Using Git Command Line (if Git is installed)

Open **PowerShell** or **Command Prompt** in the `web_app` folder and run:

```powershell
# Navigate to web_app folder
cd C:\PharmaStockApp\web_app

# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit your code
git commit -m "Initial commit - PharmaStock Web App ready for deployment"

# Add your GitHub repository as remote
git remote add origin https://github.com/JACKSON-PHARM/pharma-stock-app.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

**Note:** You'll be prompted for your GitHub username and password (or Personal Access Token).

---

### Option 2: Using GitHub Desktop (Easier - Recommended)

1. **Download GitHub Desktop**: https://desktop.github.com/
2. **Install and sign in** with your GitHub account
3. **Add Repository**:
   - Click "File" → "Add Local Repository"
   - Browse to: `C:\PharmaStockApp\web_app`
   - Click "Add Repository"
4. **Commit and Push**:
   - You'll see all your files listed
   - Enter commit message: "Initial commit - PharmaStock Web App"
   - Click "Commit to main"
   - Click "Publish repository" (or "Push origin" if already published)
   - Select: `JACKSON-PHARM/pharma-stock-app`
   - Click "Publish Repository"

---

### Option 3: Using VS Code (If you have VS Code)

1. **Open VS Code** in the `web_app` folder
2. **Open Source Control** (Ctrl+Shift+G)
3. **Initialize Repository** (if not already done):
   - Click "Initialize Repository"
4. **Stage All Files**:
   - Click "+" next to "Changes"
5. **Commit**:
   - Enter message: "Initial commit - PharmaStock Web App"
   - Click ✓ (Commit)
6. **Push**:
   - Click "..." menu → "Push"
   - Enter remote URL: `https://github.com/JACKSON-PHARM/pharma-stock-app.git`
   - Click "OK"

---

## ⚠️ Important: Before Pushing

Make sure these files are **NOT** committed (they're in `.gitignore`):
- ❌ `google_credentials.json` (sensitive - contains API keys)
- ❌ `google_token.json` (sensitive - contains auth tokens)
- ❌ `*.db` files (databases)
- ❌ `cache/` folder (local cache)

**Check:** Run `git status` to see what will be committed. Sensitive files should NOT appear.

---

## ✅ After Pushing to GitHub

Once your code is on GitHub, proceed to **Render deployment**:

1. Go to https://render.com
2. Sign up/Login with GitHub
3. Click "New +" → "Web Service"
4. Select your repository: `JACKSON-PHARM/pharma-stock-app`
5. Follow the deployment guide in `DEPLOY_TO_RENDER.md`

---

## 🆘 Troubleshooting

### "Git is not recognized"
- **Solution:** Install Git from https://git-scm.com/download/win
- Or use GitHub Desktop (Option 2 above)

### "Authentication failed"
- **Solution:** Use a Personal Access Token instead of password
- Create token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token
- Use token as password when prompted

### "Repository already exists"
- **Solution:** If you already pushed, just use: `git push origin main`

---

**Next Step:** After pushing to GitHub, follow `DEPLOY_TO_RENDER.md` to deploy on Render! 🚀

