# Francisco Lindor At-Bat Tracker

This bot tracks Francisco Lindor's at-bats and tweets the results, including detailed information about home runs and other outcomes.

## Features

- **Real-time tracking**: Monitors Francisco Lindor's at-bats during games
- **Detailed home run tweets**: Includes exit velocity, distance, launch angle, and barrel classification
- **Comprehensive stats**: Shows season totals, batting average, OPS, and advanced metrics
- **Smart rate limiting**: Avoids spamming by intelligently timing tweets
- **Situational context**: Adds game situation details to make tweets more engaging
- **Advanced metrics**: Includes wRC+, WAR, BABIP, and ISO when available
- **Multi-outcome support**: Tracks not just home runs, but hits, walks, strikeouts, and other outcomes
- **Reliable deployment**: Built for continuous operation with error handling and recovery

## Setup

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables (see below)
4. Run: `python lindor_tracker.py`

## Environment Variables

Create a `.env` file with:
```
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
TWITTER_BEARER_TOKEN=your_bearer_token
```

## What it does

- Tracks all of Francisco Lindor's at-bats
- Tweets detailed information about outcomes
- Provides real-time stats and context
- Runs continuously during baseball season 