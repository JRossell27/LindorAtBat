import os
import time
import logging
import warnings
from datetime import datetime, timezone
import tweepy
from dotenv import load_dotenv
import requests
import random
import gc  # For garbage collection
from flask import Flask, render_template
import threading
import sys
import pytz

# Suppress SyntaxWarnings from tweepy
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Set up logging with more verbose configuration for Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Ensure logs go to stdout for Render
    ]
)
logger = logging.getLogger(__name__)

# Log startup immediately
logger.info("🚀 Francisco Lindor Tracker starting up...")
logger.info(f"Python version: {sys.version}")
logger.info(f"Current working directory: {os.getcwd()}")

# Initialize Flask app
app = Flask(__name__)

# Load environment variables
load_dotenv()

# Log environment status
logger.info("📋 Environment variables loaded")
logger.info(f"PORT environment variable: {os.environ.get('PORT', 'Not set')}")

# Test mode flag
TEST_MODE = False  # Set to False for production - bot will now tweet real at-bats!

# Deployment test flag - sends one test tweet on startup
DEPLOYMENT_TEST = False  # Set to True to send a test tweet on startup, then set back to False

# Francisco Lindor's MLB ID (hardcoded to avoid lookup issues)
LINDOR_MLB_ID = 32129

logger.info(f"🎯 Configuration loaded - TEST_MODE: {TEST_MODE}, DEPLOYMENT_TEST: {DEPLOYMENT_TEST}")
logger.info(f"⚾ Tracking Francisco Lindor (ID: {LINDOR_MLB_ID})")

# Twitter API setup
if not TEST_MODE:
    try:
        # Check if environment variables exist
        required_vars = ['TWITTER_API_KEY', 'TWITTER_API_SECRET', 'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN_SECRET', 'TWITTER_BEARER_TOKEN']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"❌ Missing Twitter environment variables: {missing_vars}")
        else:
            logger.info("✅ All Twitter environment variables found")
        
        client = tweepy.Client(
            consumer_key=os.getenv('TWITTER_API_KEY'),
            consumer_secret=os.getenv('TWITTER_API_SECRET'),
            access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
            access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET'),
            bearer_token=os.getenv('TWITTER_BEARER_TOKEN')
        )
        logger.info("✅ Twitter client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Twitter client: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
else:
    logger.info("🧪 Running in TEST_MODE - Twitter client not initialized")

# Keep track of processed at-bats
processed_at_bats = set()

# Track last check time and status
last_check_time = None
last_check_status = "Initializing..."

# Cache for season stats to avoid repeated API calls
season_stats_cache = {}
cache_timestamp = None

def get_lindor_id():
    """Get Francisco Lindor's MLB ID (hardcoded for reliability)"""
    return LINDOR_MLB_ID

def get_current_game():
    """Get the current game ID if Lindor is playing"""
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": datetime.now().strftime("%m/%d/%Y")
    }
    response = requests.get(url, params=params)
    return response.json()

def get_lindor_season_stats():
    """Get Lindor's comprehensive season stats with caching"""
    global season_stats_cache, cache_timestamp
    
    # Check if cache is still valid (refresh every 10 minutes)
    if cache_timestamp and (datetime.now() - cache_timestamp).seconds < 600:
        return season_stats_cache
    
    lindor_id = get_lindor_id()
    if not lindor_id:
        return None
    
    try:
        # Get hitting stats
        url = f"https://statsapi.mlb.com/api/v1/people/{lindor_id}/stats"
        params = {
            "stats": "season",
            "season": datetime.now().year,
            "group": "hitting"
        }
        response = requests.get(url, params=params)
        hitting_data = response.json()
        
        # Get advanced stats
        params_advanced = {
            "stats": "season",
            "season": datetime.now().year,
            "group": "hitting",
            "statType": "advanced"
        }
        response_advanced = requests.get(url, params=params_advanced)
        advanced_data = response_advanced.json()
        
        # Parse and cache the stats
        stats = {}
        if hitting_data.get('stats') and len(hitting_data['stats']) > 0:
            hitting_stats = hitting_data['stats'][0]['splits'][0]['stat']
            stats.update({
                'avg': hitting_stats.get('avg', '.000'),
                'obp': hitting_stats.get('obp', '.000'),
                'slg': hitting_stats.get('slg', '.000'),
                'ops': hitting_stats.get('ops', '.000'),
                'homeRuns': hitting_stats.get('homeRuns', 0),
                'rbi': hitting_stats.get('rbi', 0),
                'runs': hitting_stats.get('runs', 0),
                'hits': hitting_stats.get('hits', 0),
                'doubles': hitting_stats.get('doubles', 0),
                'triples': hitting_stats.get('triples', 0),
                'walks': hitting_stats.get('baseOnBalls', 0),
                'strikeouts': hitting_stats.get('strikeOuts', 0),
                'stolenBases': hitting_stats.get('stolenBases', 0),
                'atBats': hitting_stats.get('atBats', 0),
                'plateAppearances': hitting_stats.get('plateAppearances', 0)
            })
        
        if advanced_data.get('stats') and len(advanced_data['stats']) > 0:
            advanced_stats = advanced_data['stats'][0]['splits'][0]['stat']
            stats.update({
                'wrc_plus': advanced_stats.get('wrcPlus', 'N/A'),
                'war': advanced_stats.get('war', 'N/A'),
                'babip': advanced_stats.get('babip', 'N/A'),
                'iso': advanced_stats.get('iso', 'N/A')
            })
        
        season_stats_cache = stats
        cache_timestamp = datetime.now()
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching season stats: {str(e)}")
        return season_stats_cache if season_stats_cache else {}

def get_situational_context():
    """Get situational context for the at-bat"""
    situations = [
        "with runners in scoring position",
        "with bases loaded",
        "with 2 outs",
        "in a clutch situation",
        "leading off the inning",
        "with a runner on first",
        "in the late innings",
        "against a lefty",
        "against a righty",
        "on a 3-2 count",
        "on the first pitch",
        "after falling behind 0-2"
    ]
    return random.choice(situations)

def calculate_ops(avg, obp, slg):
    """Calculate OPS from individual stats"""
    try:
        return round(float(obp) + float(slg), 3)
    except:
        return "N/A"

def format_tweet(play_data):
    """Format the tweet based on the play data with enhanced stats"""
    season_stats = get_lindor_season_stats()
    
    if play_data['type'] == 'home_run':
        # Enhanced home run tweet
        tweet = f"🚨 Francisco Lindor GOES YARD! 🚨\n\n"
        tweet += f"💥 Exit Velocity: {play_data['exit_velocity']} mph\n"
        tweet += f"📏 Distance: {play_data['distance']} ft\n"
        tweet += f"📐 Launch Angle: {play_data['launch_angle']}°\n"
        
        # Add barrel classification if available
        if play_data.get('barrel_classification'):
            tweet += f"🎯 {play_data['barrel_classification']}\n"
        
        # Season context
        if season_stats:
            new_hr_total = season_stats.get('homeRuns', 0) + 1
            tweet += f"\n🏆 Season HR #{new_hr_total}\n"
            tweet += f"📊 Season Stats: .{season_stats.get('avg', '000')}/{season_stats.get('obp', '.000')}/{season_stats.get('slg', '.000')}\n"
            tweet += f"💪 OPS: {season_stats.get('ops', 'N/A')}\n"
            
            if season_stats.get('rbi'):
                tweet += f"🏃 RBI: {season_stats.get('rbi', 0) + play_data.get('rbi_on_play', 1)}\n"
        
        # Situational context
        if play_data.get('situation'):
            tweet += f"⚾ {play_data['situation']}\n"
        
        tweet += f"\n#LGM"
        
    elif play_data['description'].lower() in ['single', 'double', 'triple']:
        # Enhanced hit tweet
        hit_type = play_data['description'].upper()
        emoji = "💫" if hit_type == "SINGLE" else "⚡" if hit_type == "DOUBLE" else "🔥"
        
        tweet = f"{emoji} Francisco Lindor with a {hit_type}!\n\n"
        
        # Hit data
        if play_data.get('exit_velocity') != 'N/A':
            tweet += f"💪 Exit Velocity: {play_data['exit_velocity']} mph\n"
        if play_data.get('launch_angle') != 'N/A':
            tweet += f"📐 Launch Angle: {play_data['launch_angle']}°\n"
        if play_data.get('hit_distance') != 'N/A':
            tweet += f"📏 Distance: {play_data['hit_distance']} ft\n"
        
        # Expected stats
        if play_data.get('xba'):
            tweet += f"📈 xBA: {play_data['xba']}\n"
        
        # Season context
        if season_stats:
            tweet += f"\n📊 Season: .{season_stats.get('avg', '000')} AVG, {season_stats.get('ops', 'N/A')} OPS\n"
            tweet += f"🏃 {season_stats.get('hits', 0) + 1} hits, {season_stats.get('rbi', 0)} RBI\n"
        
        tweet += f"\n#LGM"
        
    elif play_data['description'].lower() == 'walk':
        tweet = f"👁️ Francisco Lindor draws a WALK!\n\n"
        
        # Plate discipline stats
        if season_stats:
            walk_rate = round((season_stats.get('walks', 0) + 1) / season_stats.get('plateAppearances', 1) * 100, 1)
            tweet += f"🎯 Plate Discipline: {walk_rate}% BB rate\n"
            tweet += f"📊 Season: {season_stats.get('walks', 0) + 1} BB, {season_stats.get('strikeouts', 0)} K\n"
            tweet += f"👀 OBP: {season_stats.get('obp', '.000')}\n"
        
        # Situational context
        if play_data.get('situation'):
            tweet += f"⚾ {play_data['situation']}\n"
        
        tweet += f"\n#LGM"
        
    elif play_data['description'].lower() == 'strikeout':
        tweet = f"❌ Francisco Lindor strikes out"
        
        # Add strikeout type
        if play_data.get('strikeout_type') != 'N/A':
            tweet += f" {play_data['strikeout_type']}"
        
        tweet += "\n\n"
        
        # Pitch details
        if play_data.get('pitch_type') != 'N/A':
            tweet += f"🎯 Final Pitch: {play_data['pitch_type']}\n"
        if play_data.get('pitch_speed') != 'N/A':
            tweet += f"⚡ Speed: {play_data['pitch_speed']} mph\n"
        if play_data.get('pitch_location') != 'N/A':
            tweet += f"📍 Location: {play_data['pitch_location']}\n"
        
        # Season strikeout context
        if season_stats:
            k_rate = round(season_stats.get('strikeouts', 0) / season_stats.get('plateAppearances', 1) * 100, 1)
            tweet += f"\n📊 Season K Rate: {k_rate}%\n"
            tweet += f"⚾ {season_stats.get('strikeouts', 0) + 1} K, {season_stats.get('walks', 0)} BB\n"
        
        tweet += f"\n#LGM"
        
    else:
        # Generic at-bat with enhanced context
        tweet = f"⚾ Francisco Lindor: {play_data['description']}\n\n"
        
        # Add relevant stats if available
        if play_data.get('exit_velocity') != 'N/A':
            tweet += f"💪 Exit Velocity: {play_data['exit_velocity']} mph\n"
        if play_data.get('launch_angle') != 'N/A':
            tweet += f"📐 Launch Angle: {play_data['launch_angle']}°\n"
        
        # Season context
        if season_stats:
            tweet += f"\n📊 Season: .{season_stats.get('avg', '000')}/{season_stats.get('obp', '.000')}/{season_stats.get('slg', '.000')}\n"
        
        tweet += f"\n#LGM"
    
    return tweet

def keep_alive():
    """Keep the server alive by self-pinging"""
    try:
        # Update URL to match the new service name
        url = "https://lindor-at-bat-tracker.onrender.com/"
        logger.info(f"🏓 Sending keep-alive ping to {url}")
        response = requests.get(url, timeout=30)
        logger.info(f"✅ Keep-alive ping successful - Status: {response.status_code}")
    except requests.exceptions.Timeout:
        logger.error("⏰ Keep-alive ping timed out after 30 seconds")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"🔌 Keep-alive ping connection error: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Keep-alive ping failed: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")

def send_deployment_test_tweet():
    """Send a one-time test tweet on deployment"""
    try:
        test_tweet = f"""🚀 Francisco Lindor Bot - Deployment Test

✅ Bot successfully deployed and running!
📅 Deployed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
⚾ Ready to track Francisco Lindor's at-bats!

🤖 This is an automated deployment test
🗑️ Will be manually deleted

#LGM"""
        
        if not TEST_MODE:
            response = client.create_tweet(text=test_tweet)
            logger.info(f"🚀 DEPLOYMENT TEST TWEET SENT! Tweet ID: {response.data['id']}")
            logger.info(f"Tweet URL: https://twitter.com/user/status/{response.data['id']}")
            return True
        else:
            logger.info(f"TEST MODE - Would send deployment test tweet: {test_tweet}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send deployment test tweet: {str(e)}")
        return False

def generate_test_at_bat():
    """Generate a test at-bat with enhanced random data"""
    is_home_run = random.random() < 0.25  # 25% chance of home run
    
    if is_home_run:
        return {
            'events': 'home_run',
            'description': 'Home Run',
            'launch_speed': round(random.uniform(100, 118), 1),
            'launch_angle': round(random.uniform(22, 35), 1),
            'hit_distance_sc': round(random.uniform(380, 470)),
            'barrel': random.randint(25, 35),
            'home_run': random.randint(1, 35),
            'game_date': datetime.now().strftime("%Y-%m-%d"),
            'inning': random.randint(1, 9),
            'at_bat_number': random.randint(1, 5),
            'barrel_classification': random.choice(['Barrel', 'Solid Contact', 'Hard Hit']),
            'xba': round(random.uniform(0.8, 1.0), 3),
            'situation': get_situational_context(),
            'rbi_on_play': random.randint(1, 4)
        }
    else:
        outcomes = ['Single', 'Double', 'Triple', 'Strikeout', 'Walk', 'Groundout', 'Flyout', 'Line Out']
        outcome = random.choice(outcomes)
        result = {
            'events': outcome.lower(),
            'description': outcome,
            'launch_speed': round(random.uniform(65, 115), 1),
            'launch_angle': round(random.uniform(-15, 45), 1),
            'game_date': datetime.now().strftime("%Y-%m-%d"),
            'inning': random.randint(1, 9),
            'at_bat_number': random.randint(1, 5),
            'situation': get_situational_context()
        }
        
        # Add hit-specific data
        if outcome in ['Single', 'Double', 'Triple']:
            result.update({
                'hit_distance': round(random.uniform(200, 350)),
                'xba': round(random.uniform(0.1, 0.9), 3),
                'rbi_on_play': random.randint(0, 2) if outcome != 'Triple' else random.randint(1, 3)
            })
        
        # Add strikeout-specific data
        elif outcome == 'Strikeout':
            result.update({
                'strikeout_type': random.choice(['looking', 'swinging']),
                'pitch_type': random.choice(['4-Seam Fastball', 'Slider', 'Curveball', 'Changeup', 'Cutter', 'Sinker', 'Knuckle Curve']),
                'pitch_speed': round(random.uniform(82, 101), 1),
                'pitch_location': random.choice(['High and Inside', 'Low and Away', 'Middle-In', 'Middle-Out', 'High and Away', 'Low and In', 'Up in the Zone'])
            })
        
        return result

def check_lindor_at_bats():
    """Check for Lindor's at-bats and tweet if found"""
    global last_check_time, last_check_status
    
    try:
        lindor_id = get_lindor_id()
        logger.info("Checking for Lindor at-bats...")
        
        # Add comprehensive time/date logging
        utc_now = datetime.now(timezone.utc)
        et_now = utc_now.astimezone(pytz.timezone('US/Eastern'))
        
        logger.info(f"🕐 Current UTC time: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"🕐 Current ET time: {et_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Use Eastern Time for MLB games
        today_et = et_now.strftime("%Y-%m-%d")
        logger.info(f"🗓️ Using date for MLB lookup: {today_et}")
        
        if TEST_MODE:
            # Generate test at-bat with enhanced data
            test_at_bat = generate_test_at_bat()
            at_bat_id = f"{test_at_bat['game_date']}_{test_at_bat['inning']}_{test_at_bat['at_bat_number']}"
            
            logger.info(f"Generated test at-bat: {test_at_bat['description']} (ID: {at_bat_id})")
            
            if at_bat_id not in processed_at_bats:
                logger.info(f"New at-bat found! Processing: {test_at_bat['description']}")
                
                play_data = {
                    'type': 'home_run' if test_at_bat['events'] == 'home_run' else 'other',
                    'description': test_at_bat['description'],
                    'exit_velocity': test_at_bat.get('launch_speed', 'N/A'),
                    'launch_angle': test_at_bat.get('launch_angle', 'N/A'),
                    'distance': test_at_bat.get('hit_distance_sc', 'N/A'),
                    'parks': test_at_bat.get('barrel', 'N/A'),
                    'hr_number': test_at_bat.get('home_run', 0),
                    'situation': test_at_bat.get('situation', ''),
                    'barrel_classification': test_at_bat.get('barrel_classification', ''),
                    'xba': test_at_bat.get('xba', 'N/A'),
                    'hit_distance': test_at_bat.get('hit_distance', 'N/A'),
                    'rbi_on_play': test_at_bat.get('rbi_on_play', 0)
                }
                
                # Add strikeout data if it's a strikeout
                if test_at_bat['events'] == 'strikeout':
                    play_data.update({
                        'strikeout_type': test_at_bat.get('strikeout_type', 'N/A'),
                        'pitch_type': test_at_bat.get('pitch_type', 'N/A'),
                        'pitch_speed': test_at_bat.get('pitch_speed', 'N/A'),
                        'pitch_location': test_at_bat.get('pitch_location', 'N/A')
                    })
                
                tweet = format_tweet(play_data)
                if TEST_MODE:
                    logger.info(f"TEST MODE - Would tweet: {tweet}")
                else:
                    client.create_tweet(text=tweet)
                    logger.info(f"Tweeted: {tweet}")
                
                processed_at_bats.add(at_bat_id)
                last_check_status = f"Found test at-bat: {test_at_bat['description']} {test_at_bat.get('situation', '')}"
                logger.info(f"At-bat processed and added to cache. Total processed: {len(processed_at_bats)}")
            else:
                logger.info(f"At-bat already processed (ID: {at_bat_id}). Skipping...")
                last_check_status = f"Duplicate at-bat skipped: {test_at_bat['description']}"
        else:
            # Check today's games first
            logger.info(f"🗓️ Checking for Mets games on {today_et}")
            
            # Get today's schedule to see if Mets are playing
            schedule_url = "https://statsapi.mlb.com/api/v1/schedule"
            schedule_params = {
                "sportId": 1,
                "date": today_et,
                "teamId": 121  # New York Mets team ID
            }
            
            try:
                schedule_response = requests.get(schedule_url, params=schedule_params)
                schedule_data = schedule_response.json()
                logger.info(f"📋 Schedule API response: {schedule_data}")
                
                if schedule_data.get('dates') and len(schedule_data['dates']) > 0:
                    games_today = schedule_data['dates'][0].get('games', [])
                    logger.info(f"🎮 Found {len(games_today)} Mets games today")
                    
                    for game in games_today:
                        game_state = game.get('status', {}).get('detailedState', 'Unknown')
                        game_time = game.get('gameDate', 'Unknown')
                        home_team = game.get('teams', {}).get('home', {}).get('team', {}).get('name', 'Unknown')
                        away_team = game.get('teams', {}).get('away', {}).get('team', {}).get('name', 'Unknown')
                        
                        logger.info(f"🏟️ Game: {away_team} @ {home_team}")
                        logger.info(f"🕐 Game time: {game_time}")
                        logger.info(f"🎯 Game status: {game_state}")
                        
                        # If there's a game today, get more detailed info
                        if game_state in ['Preview', 'Pre-Game', 'Warmup', 'In Progress', 'Final', 'Game Over']:
                            game_pk = game.get('gamePk')
                            logger.info(f"🔍 Getting detailed data for game {game_pk}...")
                            
                            # Try the play-by-play API for live at-bat data
                            pbp_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
                            try:
                                pbp_response = requests.get(pbp_url)
                                pbp_data = pbp_response.json()
                                
                                logger.info(f"📊 Play-by-play data keys: {list(pbp_data.keys()) if pbp_data else 'No data'}")
                                
                                if pbp_data.get('liveData'):
                                    live_data = pbp_data['liveData']
                                    logger.info(f"🔴 Live data keys: {list(live_data.keys())}")
                                    
                                    # Check for plays
                                    if live_data.get('plays'):
                                        plays = live_data['plays']
                                        all_plays = plays.get('allPlays', [])
                                        logger.info(f"🎭 Found {len(all_plays)} total plays in game")
                                        
                                        # Look for Lindor's at-bats
                                        for play in all_plays:
                                            batter = play.get('matchup', {}).get('batter', {})
                                            batter_id = batter.get('id')
                                            batter_name = batter.get('fullName', 'Unknown')
                                            
                                            if str(batter_id) == str(lindor_id):
                                                logger.info(f"⚾ Found Lindor at-bat: {play.get('result', {}).get('description', 'Unknown')}")
                                                logger.info(f"📋 Play details: {play}")
                                                # Process this at-bat...
                                            
                            except Exception as e:
                                logger.error(f"❌ Error getting play-by-play data: {str(e)}")
                                
                else:
                    logger.info("📅 No Mets games scheduled for today")
                    
            except Exception as e:
                logger.error(f"❌ Error checking schedule: {str(e)}")
            
            # Get Lindor's recent at-bats with enhanced data
            logger.info("🔍 Checking MLB API for Lindor's recent at-bats...")
            url = f"https://statsapi.mlb.com/api/v1/people/{lindor_id}/stats"
            params = {
                "stats": "gameLog",
                "season": datetime.now().year,
                "group": "hitting"
            }
            
            try:
                response = requests.get(url, params=params)
                recent_at_bats = response.json()
                logger.info(f"📊 Stats API response structure: {list(recent_at_bats.keys()) if recent_at_bats else 'No data'}")
                
                if recent_at_bats and 'stats' in recent_at_bats:
                    logger.info(f"📈 Found {len(recent_at_bats['stats'])} stat groups")
                    
                    for stat_group in recent_at_bats['stats']:
                        splits = stat_group.get('splits', [])
                        logger.info(f"🎯 Found {len(splits)} games in stat group")
                        
                        for game_log in splits:
                            game_date = game_log.get('date', 'unknown')
                            logger.info(f"📅 Game date: {game_date}, Today: {today_et}")
                            
                            if game_date == today_et:
                                logger.info(f"✅ Found today's game! Stats: {game_log.get('stat', {})}")
                                # Process the game log data here
                            else:
                                logger.info(f"⏭️ Skipping game from {game_date}")
                else:
                    logger.info("❌ No stats data found in API response")
                    
            except Exception as e:
                logger.error(f"❌ Error fetching stats: {str(e)}")
            
            # Also try live game feed API
            logger.info("🔴 Checking live game feed...")
            try:
                live_url = "https://statsapi.mlb.com/api/v1/schedule"
                live_params = {
                    "sportId": 1,
                    "date": today_et,
                    "hydrate": "game(linescore,boxscore),team"
                }
                live_response = requests.get(live_url, params=live_params)
                live_data = live_response.json()
                
                logger.info(f"🔴 Live data structure: {list(live_data.keys()) if live_data else 'No data'}")
                
                if live_data.get('dates'):
                    for date_entry in live_data['dates']:
                        games = date_entry.get('games', [])
                        logger.info(f"🎮 Found {len(games)} games in live feed")
                        
                        for game in games:
                            # Check if this game involves the Mets
                            home_team = game.get('teams', {}).get('home', {}).get('team', {}).get('name', '')
                            away_team = game.get('teams', {}).get('away', {}).get('team', {}).get('name', '')
                            
                            if 'Mets' in home_team or 'Mets' in away_team:
                                logger.info(f"🏟️ Found Mets game: {away_team} @ {home_team}")
                                game_state = game.get('status', {}).get('detailedState', 'Unknown')
                                logger.info(f"🎯 Game state: {game_state}")
                                
                                # If game is in progress or final, check for at-bats
                                if game_state in ['In Progress', 'Final', 'Game Over']:
                                    game_pk = game.get('gamePk')
                                    logger.info(f"🔍 Checking game {game_pk} for Lindor at-bats...")
                                    
                                    # Get detailed game data
                                    game_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                                    game_response = requests.get(game_url)
                                    game_data = game_response.json()
                                    
                                    logger.info(f"📦 Game data keys: {list(game_data.keys()) if game_data else 'No data'}")
                                    
            except Exception as e:
                logger.error(f"❌ Error checking live games: {str(e)}")
            
            last_check_status = "No new at-bats found"
            logger.info("No new at-bats found in MLB API")
        
        last_check_time = datetime.now()
        logger.info(f"Check completed. Status: {last_check_status}")
        
    except Exception as e:
        error_msg = f"Error occurred: {str(e)}"
        logger.error(error_msg)
        last_check_status = error_msg

def background_checker():
    """Background thread to check for Lindor's at-bats and keep service alive"""
    logger.info("🔄 Background checker thread started")
    ping_counter = 0
    cycle_count = 0
    
    while True:
        try:
            cycle_count += 1
            logger.info(f"🔍 Starting check cycle #{cycle_count}")
            
            # Check for at-bats
            check_lindor_at_bats()
            
            # Send keep-alive ping every 4 minutes (2 cycles of 2 minutes each)
            # This ensures we ping well before Render's 15-minute timeout
            ping_counter += 1
            logger.info(f"📊 Ping counter: {ping_counter}/2")
            
            if ping_counter >= 2:
                logger.info("🏓 Time for keep-alive ping")
                keep_alive()
                ping_counter = 0
            
            logger.info(f"😴 Sleeping for 2 minutes until next check...")
            time.sleep(120)  # Wait 2 minutes between checks
            
        except Exception as e:
            logger.error(f"❌ Error in background checker: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.info("🔄 Continuing background checker despite error...")
            time.sleep(120)  # Still wait before retrying

@app.route('/')
def home():
    """Render the home page with status information"""
    global last_check_time, last_check_status
    
    logger.info("📱 Home page accessed")
    
    if last_check_time is None:
        status = "Initializing..."
    else:
        status = f"Last check: {last_check_time.strftime('%Y-%m-%d %H:%M:%S')} - {last_check_status}"
    
    return f"""
    <html>
        <head>
            <title>Francisco Lindor HR Tracker</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background-color: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #002D72;
                    text-align: center;
                }}
                .status {{
                    margin-top: 20px;
                    padding: 15px;
                    background-color: #f8f9fa;
                    border-radius: 5px;
                    border-left: 5px solid #002D72;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Francisco Lindor HR Tracker</h1>
                <div class="status">
                    <p><strong>Status:</strong> {status}</p>
                    <p><strong>Mode:</strong> {'TEST' if TEST_MODE else 'PRODUCTION'}</p>
                    <p><strong>Processed At-Bats:</strong> {len(processed_at_bats)}</p>
                    <p><strong>Uptime:</strong> Service is running</p>
                </div>
                <div style="margin-top: 20px;">
                    <a href="/health" style="color: #002D72;">Health Check</a>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    logger.info("🏥 Health check accessed")
    return {
        "status": "healthy",
        "service": "Francisco Lindor HR Tracker",
        "timestamp": datetime.now().isoformat(),
        "test_mode": TEST_MODE,
        "processed_at_bats": len(processed_at_bats),
        "last_check": last_check_time.isoformat() if last_check_time else None,
        "last_status": last_check_status
    }

if __name__ == "__main__":
    logger.info("🚀 Starting Francisco Lindor HR Tracker...")
    logger.info(f"🎯 TEST_MODE: {TEST_MODE}")
    logger.info(f"🧪 DEPLOYMENT_TEST: {DEPLOYMENT_TEST}")
    logger.info(f"⚾ LINDOR_MLB_ID: {LINDOR_MLB_ID}")
    logger.info(f"🌍 Environment: {'Render' if os.environ.get('RENDER') else 'Local'}")
    
    # Send deployment test tweet if enabled
    if DEPLOYMENT_TEST and not TEST_MODE:
        logger.info("🚀 Sending deployment test tweet...")
        if send_deployment_test_tweet():
            logger.info("✅ Deployment test tweet sent successfully!")
        else:
            logger.error("❌ Failed to send deployment test tweet")
    elif DEPLOYMENT_TEST and TEST_MODE:
        logger.info("⚠️ DEPLOYMENT_TEST enabled but in TEST_MODE - no tweet will be sent")
    else:
        logger.info("ℹ️ DEPLOYMENT_TEST disabled - no test tweet will be sent")
    
    # Start the background checker thread
    logger.info("🔄 Starting background checker thread...")
    try:
        checker_thread = threading.Thread(target=background_checker, daemon=True)
        checker_thread.start()
        logger.info("✅ Background checker thread started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start background checker thread: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
    
    # Start the Flask app
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Starting Flask app on host=0.0.0.0, port={port}...")
    logger.info(f"🔗 Service will be available at: https://lindor-at-bat-tracker.onrender.com/")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"❌ Flask app failed to start: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        raise 