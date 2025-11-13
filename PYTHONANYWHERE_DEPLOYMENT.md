# PythonAnywhere Deployment Guide

## Prerequisites
- PythonAnywhere account (free or paid)
- GitHub repository cloned to PythonAnywhere

## Step-by-Step Deployment

### 1. Initial Setup After Cloning

After cloning the repo, navigate to your project directory:
```bash
cd ~/HACKKU24
```

### 2. Create and Activate Virtual Environment

```bash
mkvirtualenv --python=/usr/bin/python3.10 hackku24-env
workon hackku24-env
```

Or if using Python 3.11:
```bash
mkvirtualenv --python=/usr/bin/python3.11 hackku24-env
workon hackku24-env
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If you don't have a requirements.txt, create one with:
```bash
pip install flask flask-sqlalchemy flask-mail python-dotenv requests matplotlib numpy pandas yfinance
pip freeze > requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in your project root:
```bash
nano .env
```

Add your configuration (use your actual values):
```env
# Flask Configuration
SECRET_KEY=your-secret-key-here

# Database
SQLALCHEMY_DATABASE_URI=sqlite:///instance/users.db

# Email Configuration (Gmail)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_gmail_app_password
MAIL_USE_TLS=True
MAIL_USE_SSL=False

# API Keys
ALPHAVANTAGE_API_KEY=A0QB6IBTEOUO7W98
MEDIASTACK_API_KEY=92326870a786707523889fb694ad68e2
```

Save with `Ctrl+O`, `Enter`, then `Ctrl+X`

### 5. Create Instance Directory and Initialize Database

```bash
mkdir -p instance
python3 -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database created!')"
```

### 6. Set Up Web App on PythonAnywhere

#### Go to the Web tab in PythonAnywhere Dashboard:

1. Click **"Add a new web app"**
2. Choose **"Manual configuration"** (not Flask wizard)
3. Select **Python 3.10** or **3.11**

#### Configure the Web App:

**Source Code Directory:**
```
/home/YOUR_USERNAME/HACKKU24
```

**Working Directory:**
```
/home/YOUR_USERNAME/HACKKU24
```

**Virtualenv:**
```
/home/YOUR_USERNAME/.virtualenvs/hackku24-env
```

### 7. Configure WSGI File

Click on the **WSGI configuration file** link and replace its contents with:

```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/YOUR_USERNAME/HACKKU24'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Set environment variable to load .env file
os.chdir(project_home)

# Import Flask app
from app import app as application

# Set up Flask app context
application.app_context().push()
```

**Replace `YOUR_USERNAME`** with your actual PythonAnywhere username.

Save the file.

### 8. Set Up Static Files (Optional)

In the **Web** tab, under **Static files**:
- URL: `/static/`
- Directory: `/home/YOUR_USERNAME/HACKKU24/static`

### 9. Reload the Web App

Click the green **"Reload"** button on the Web tab.

### 10. Set Up Scheduled Tasks for Email Sending

Go to the **Tasks** tab in PythonAnywhere:

Add a scheduled task to run `main.py` daily:

**Command:**
```bash
cd /home/YOUR_USERNAME/HACKKU24 && /home/YOUR_USERNAME/.virtualenvs/hackku24-env/bin/python main.py
```

**Schedule:** 
- Choose the time you want emails sent (e.g., "08:00" for 8 AM UTC)

### 11. Test Your Application

Visit your PythonAnywhere URL:
```
https://YOUR_USERNAME.pythonanywhere.com
```

## Troubleshooting

### Check Error Logs

View error logs in the **Web** tab:
- Click on **"Error log"** link
- Check for any Python errors

### Common Issues

#### 1. Import Errors
If you see import errors, make sure all packages are installed:
```bash
workon hackku24-env
pip install -r requirements.txt
```

#### 2. Database Not Found
Create the instance directory and database:
```bash
mkdir -p instance
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
```

#### 3. .env File Not Loading
Make sure the `.env` file is in the project root and `python-dotenv` is installed:
```bash
pip install python-dotenv
```

#### 4. Permission Issues
Ensure the instance directory is writable:
```bash
chmod 755 instance
```

#### 5. Email Not Sending
- Make sure you're using a Gmail **App Password**, not your regular password
- Enable 2-factor authentication on your Google account
- Generate an app-specific password from: https://myaccount.google.com/apppasswords

### Test Email Sending Manually

```bash
workon hackku24-env
cd ~/HACKKU24
python main.py
```

Check the output for any errors.

## File Structure

Your PythonAnywhere directory should look like:
```
/home/YOUR_USERNAME/HACKKU24/
├── app.py
├── main.py
├── config.py
├── .env
├── requirements.txt
├── instance/
│   └── users.db
├── static/
│   └── style.css
└── templates/
    ├── index.html
    ├── change.html
    ├── daily_mail.html
    ├── email_content.html
    ├── sameuser.html
    ├── success.html
    └── unsub.html
```

## Important Notes

### Free Account Limitations:
- **No outbound internet from scheduled tasks** - Emails won't work on free tier
- **Limited CPU time**
- You'll need a **paid account** ($5/month) to:
  - Send emails from scheduled tasks
  - Make API calls to Alpha Vantage and MediaStack
  - Run `main.py` as a scheduled task

### For Free Tier Users:
You can still:
- Run the Flask web app for user registration
- Test `main.py` manually from the Bash console
- Use the web interface

But automated email sending requires a paid account.

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | `your-random-secret-key` |
| `SQLALCHEMY_DATABASE_URI` | Database path | `sqlite:///instance/users.db` |
| `MAIL_SERVER` | SMTP server | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USERNAME` | Your email | `your_email@gmail.com` |
| `MAIL_PASSWORD` | Gmail app password | `xxxx xxxx xxxx xxxx` |
| `MAIL_USE_TLS` | Use TLS | `True` |
| `ALPHAVANTAGE_API_KEY` | Alpha Vantage API key | `A0QB6IBTEOUO7W98` |
| `MEDIASTACK_API_KEY` | MediaStack API key | `92326870a786707523889fb694ad68e2` |

## Quick Command Reference

```bash
# Activate virtual environment
workon hackku24-env

# Update from GitHub
cd ~/HACKKU24
git pull origin main

# Install/update dependencies
pip install -r requirements.txt

# Run migrations (if database schema changed)
python remove_insider_column.py

# Test email sending manually
python main.py

# Check Python version
python --version

# List installed packages
pip list

# Deactivate virtual environment
deactivate
```

## Need Help?

- Check PythonAnywhere forums: https://www.pythonanywhere.com/forums/
- Review error logs in the Web tab
- Test components individually in the Bash console
