# AnyNews - Feature Updates

## New Features Added

### 1. Market Charts Integration
- Users can now opt-in to receive daily market charts with their news updates
- Charts include:
  - **S&P 500** (^GSPC)
  - **NASDAQ** (^IXIC)
  - **Bitcoin** (BTC-USD)
- All charts show 90-day candlestick data
- Charts are generated using yfinance and matplotlib

### 2. Token-Based Authentication
- Users no longer need to re-enter their email for account management
- Each user receives a unique secure token
- Token is used for:
  - Updating preferences
  - Unsubscribing from emails
  - Accessing user settings

## How to Use

### For New Users
1. Visit the homepage
2. Enter your email and topics of interest
3. **NEW:** Check "Include daily market charts" if you want market data
4. Submit the form

### For Existing Users
- When you enter an email that's already registered, you'll be redirected to your account page
- From there you can:
  - Update your topics
  - Toggle chart preferences on/off
  - Unsubscribe

### Token-Based Links
All email management links now use tokens, so you don't need to enter your email again:
- Update preferences link: `/update_info?token=YOUR_TOKEN`
- Unsubscribe link: `/unsubscribe?token=YOUR_TOKEN`

## Technical Changes

### Database Schema
- Added `include_charts` BOOLEAN column to the `user` table
- Run `migrate_db.py` to update existing databases

### New Dependencies
```
yfinance==0.2.32
matplotlib==3.8.2
pandas==2.1.4
```

### Files Modified
- `app.py` - Updated User model and routes for token-based auth
- `main.py` - Added chart generation with yfinance/matplotlib
- `templates/index.html` - Added chart preference checkbox
- `templates/change.html` - Updated to use tokens and show current settings
- `templates/sameuser.html` - Updated to use token-based links
- `templates/unsub.html` - Improved UX with token confirmation
- `templates/daily_mail.html` - Added chart display section

### Security Improvements
- All user management actions now use secure tokens
- Email addresses are pre-filled and readonly in update forms
- No more manual email entry for authenticated actions

## Migration Instructions

If you have an existing database:
```bash
python migrate_db.py
```

This will add the `include_charts` column to your existing user table.

## Chart Generation Details

- Charts are generated once per day (when main.py runs)
- If any user has charts enabled, they are generated for all users who want them
- Charts are embedded as base64-encoded images in emails
- Non-interactive backend (Agg) is used for server environments
- Automatic error handling if chart generation fails

## Performance Notes

- Chart generation adds ~10-15 seconds to the email sending process
- Charts are only generated if at least one user has them enabled
- Failed chart generation won't prevent emails from being sent
