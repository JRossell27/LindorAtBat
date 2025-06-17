# Pete Alonso At-Bat Tracker

This bot tracks Pete Alonso's at-bats and tweets the results, including detailed information about home runs and other outcomes.

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with the following variables:
   ```
   TWITTER_API_KEY=your_api_key
   TWITTER_API_SECRET=your_api_secret
   TWITTER_ACCESS_TOKEN=your_access_token
   TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
   TWITTER_BEARER_TOKEN=your_bearer_token
   ```

## Running Locally

```bash
python alonso_tracker.py
```

## Deployment

This bot is designed to run on Render.com. The free tier will spin down with inactivity, but the bot includes a keep-alive mechanism to prevent this.

## Features

- Tracks all of Pete Alonso's at-bats
- Tweets detailed information about each at-bat
- For home runs: includes exit velocity, distance, launch angle, and number of parks it would have been a home run in
- For other outcomes: includes the result and relevant statistics 