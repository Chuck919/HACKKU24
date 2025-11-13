# Token-Based URL Structure

## Overview
All user management actions now use secure tokens instead of requiring email re-entry. Each user has a unique `unsubscribe_token` that's generated when they sign up.

## URL Patterns

### 1. Update Preferences
**URL:** `/update_info?token=<USER_TOKEN>`

**Example:**
```
https://yoursite.com/update_info?token=AbC123dEf456
```

**What it does:**
- Shows current email (readonly)
- Shows current topics (editable)
- Shows chart preference (toggle)
- Updates user preferences on submit

---

### 2. Unsubscribe
**URL:** `/unsubscribe?token=<USER_TOKEN>`

**Example:**
```
https://yoursite.com/unsubscribe?token=AbC123dEf456
```

**What it does:**
- Shows confirmation page with user's email
- Deletes user from database on confirmation
- No email entry required!

---

### 3. Existing User (Returning)
**URL:** `/sameuser?token=<USER_TOKEN>`

**Example:**
```
https://yoursite.com/sameuser?token=AbC123dEf456
```

**What it does:**
- Shows welcome back message
- Provides links to update preferences
- Provides link to unsubscribe

---

## How Tokens Are Generated

```python
import secrets

# In app.py User model
def __init__(self, email, text, include_charts=False):
    self.email = email
    self.text = text
    self.include_charts = include_charts
    self.unsubscribe_token = secrets.token_urlsafe(16)
```

**Token Properties:**
- 16-byte URL-safe random string
- Unpredictable and secure
- Unique per user (database constraint)
- Stored in database

---

## Email Templates

### Welcome Email (from app.py)
```html
<!-- In email_content.html -->
<p>
  To update your preferences: 
  <a href="{{ unsubscribe_link }}">Click here</a>
</p>
<p>
  Return to homepage: 
  <a href="{{ homepage_link }}">Click here</a>
</p>
```

### Daily News Email (from main.py)
```html
<!-- In daily_mail.html -->
<p>
  If you no longer wish to receive emails: 
  <a href="https://yoursite.com/unsubscribe?token=USER_TOKEN">unsubscribe</a>
</p>
```

---

## Security Benefits

✅ **No email exposure** - Users don't type emails in URLs or forms
✅ **Unique per user** - Each user has their own secret token
✅ **Unpredictable** - Tokens are cryptographically random
✅ **One-click actions** - Users can manage preferences with one click
✅ **Database-backed** - Tokens verified against database

---

## Fallback Options

Even without a token, users can still:
1. Enter email on homepage → redirected to settings
2. Manually enter email on unsubscribe page

---

## Database Lookup

```python
# Find user by token
user = User.query.filter_by(unsubscribe_token=token).first()

if user:
    # Token is valid, proceed
    email = user.email
    topics = user.text
    charts_enabled = user.include_charts
else:
    # Invalid token
    flash('Invalid access token', 'error')
    redirect to homepage
```

---

## Example User Flow

1. **User signs up:**
   - Email: user@example.com
   - Topics: bitcoin, stocks
   - Charts: ✓ Enabled
   - Token generated: `Xy9_AbC-123def45`

2. **User receives welcome email:**
   - Contains link: `/update_info?token=Xy9_AbC-123def45`

3. **User clicks link:**
   - Taken to settings page
   - Email pre-filled (readonly)
   - Topics pre-filled (editable)
   - Charts checkbox checked
   - Can update and submit

4. **User wants to unsubscribe:**
   - Clicks unsubscribe in daily email
   - Link: `/unsubscribe?token=Xy9_AbC-123def45`
   - Sees confirmation: "Unsubscribe user@example.com?"
   - Clicks confirm
   - Deleted from database

---

## Testing Tokens

To get a user's token for testing:

```python
from app import app, db, User

with app.app_context():
    user = User.query.filter_by(email='test@example.com').first()
    print(f"Token: {user.unsubscribe_token}")
```

Then visit:
```
http://localhost:5000/update_info?token=<TOKEN>
http://localhost:5000/unsubscribe?token=<TOKEN>
```
