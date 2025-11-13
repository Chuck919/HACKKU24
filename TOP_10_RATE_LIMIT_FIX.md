# Top 10 S&P 500 Stocks - Rate Limiting Fix

## Problem
The Alpha Vantage API was only returning data for the first stock (AAPL) and showing "No data returned from API" for the rest. This was due to hitting the API rate limit of **5 calls per minute**.

## Solution
Added proper rate limiting with a 13-second delay between API calls to stay within the 5 calls/minute limit.

## Changes Made

### 1. Updated `main.py`
- **Added import**: `import time` to enable sleep functionality
- **Updated `fetch_top10_sp500_stocks()` function**:
  - Added 13-second wait between API calls (5 calls/min = 12 sec/call, using 13 for safety)
  - Added progress indicator showing `[X/10]` for each stock
  - Added detection for rate limit messages ("Note" or "Information" in response)
  - If rate limited, waits 60 seconds before continuing
  - Function now takes approximately **2 minutes** to fetch all 10 stocks

### 2. Created `test_alpha_vantage.py`
A dedicated test script to validate the API for all 10 stocks individually:
- Tests each ticker with proper rate limiting
- Shows detailed response data for debugging
- Displays S&P 500 weights for each stock
- Provides comprehensive error handling
- Takes ~2 minutes to complete (13 seconds × 10 stocks)

## Top 10 S&P 500 Stocks (by Index Weight)

The stocks are ordered by their actual percentage weight in the S&P 500 index:

1. **AAPL** (Apple) - ~7.1%
2. **MSFT** (Microsoft) - ~6.8%
3. **NVDA** (NVIDIA) - ~6.2%
4. **AMZN** (Amazon) - ~3.8%
5. **META** (Meta) - ~2.6%
6. **GOOGL** (Alphabet A) - ~2.1%
7. **TSLA** (Tesla) - ~1.8%
8. **BRK.B** (Berkshire Hathaway B) - ~1.7%
9. **LLY** (Eli Lilly) - ~1.5%
10. **AVGO** (Broadcom) - ~1.4%

## Usage

### Testing the API
Run the test script to verify all stocks are accessible:
```powershell
python test_alpha_vantage.py
```

This will:
- Test each stock individually with 13-second delays
- Show detailed API response data
- Display success/failure for each ticker
- Provide a summary at the end

**Expected Duration**: ~2 minutes

### Running the Main Application
When you run `main.py`, the Top 10 stocks will be fetched with automatic rate limiting:
```powershell
python main.py
```

You'll see output like:
```
Fetching Top 10 S&P 500 stocks...
NOTE: Rate limit is 5 calls/minute, this will take ~2 minutes
  SUCCESS: AAPL: $273.47 (-0.65%)
  [1/10] Waiting 13s for rate limit...
  SUCCESS: MSFT: $425.32 (+1.23%)
  [2/10] Waiting 13s for rate limit...
  ...
```

## API Rate Limits

### Alpha Vantage Free Tier
- **5 API calls per minute**
- **500 API calls per day**

### Implications
- Fetching 10 stocks = 10 API calls = ~2 minutes
- With charts (SP500, NASDAQ, Bitcoin) = 3 additional calls
- With market news = 1 additional call
- **Total per email run**: ~14 API calls (~3 minutes)

## Fallback Behavior
If fewer than 5 stocks successfully fetch:
- The system automatically falls back to **mock data**
- Mock data includes realistic price movements
- All 10 stocks will be displayed with simulated changes

## Notes
- The 13-second delay ensures we stay under the 5 calls/minute limit
- Markets are only open during trading hours (9:30 AM - 4:00 PM ET)
- Outside trading hours, prices will show the previous close data
