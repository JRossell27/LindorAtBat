import os
import time
import logging
import warnings
from datetime import datetime
import tweepy
from dotenv import load_dotenv
import requests
import random
import gc  # For garbage collection
from flask import Flask, render_template
import threading

# Suppress SyntaxWarnings from tweepy
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Load environment variables
load_dotenv()

# Test mode flag
TEST_MODE = True  # Set to True for now to avoid API calls during startup

# Juan Soto's MLB ID (hardcoded to avoid lookup issues)
SOTO_MLB_ID = 665742

# Twitter API setup
if not TEST_MODE:
    try:
        client = tweepy.Client(
            consumer_key=os.getenv('TWITTER_API_KEY'),
            consumer_secret=os.getenv('TWITTER_API_SECRET'),
            access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
            access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET'),
            bearer_token=os.getenv('TWITTER_BEARER_TOKEN')
        )
        logger.info("Twitter client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twitter client: {str(e)}")

# Keep track of processed at-bats
processed_at_bats = set()

# Track last check time and status
last_check_time = None
last_check_status = "Initializing..."

# Cache for season stats to avoid repeated API calls
season_stats_cache = {}
cache_timestamp = None

def get_soto_id():
    """Get Juan Soto's MLB ID (hardcoded for reliability)"""
    return SOTO_MLB_ID

def get_current_game():
    """Get the current game ID if Soto is playing"""
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": datetime.now().strftime("%m/%d/%Y")
    }
    response = requests.get(url, params=params)
    return response.json()

def get_soto_season_stats():
    """Get Soto's comprehensive season stats with caching"""
    global season_stats_cache, cache_timestamp
    
    # Check if cache is still valid (refresh every 10 minutes)
    if cache_timestamp and (datetime.now() - cache_timestamp).seconds < 600:
        return season_stats_cache
    
    soto_id = get_soto_id()
    if not soto_id:
        return None
    
    try:
        # Get hitting stats
        url = f"https://statsapi.mlb.com/api/v1/people/{soto_id}/stats"
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
    season_stats = get_soto_season_stats()
    
    if play_data['type'] == 'home_run':
        # Enhanced home run tweet
        tweet = f"🚨 JUAN SOTO GOES YARD! 🚨\n\n"
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
        
        tweet += f"\n#JuanSoto #Mets #MLB #HomeRun"
        
    elif play_data['description'].lower() in ['single', 'double', 'triple']:
        # Enhanced hit tweet
        hit_type = play_data['description'].upper()
        emoji = "💫" if hit_type == "SINGLE" else "⚡" if hit_type == "DOUBLE" else "🔥"
        
        tweet = f"{emoji} Juan Soto with a {hit_type}!\n\n"
        
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
        
        tweet += f"\n#JuanSoto #Mets #MLB"
        
    elif play_data['description'].lower() == 'walk':
        tweet = f"👁️ Juan Soto draws a WALK!\n\n"
        
        # Plate discipline stats
        if season_stats:
            walk_rate = round((season_stats.get('walks', 0) + 1) / season_stats.get('plateAppearances', 1) * 100, 1)
            tweet += f"🎯 Plate Discipline: {walk_rate}% BB rate\n"
            tweet += f"📊 Season: {season_stats.get('walks', 0) + 1} BB, {season_stats.get('strikeouts', 0)} K\n"
            tweet += f"👀 OBP: {season_stats.get('obp', '.000')}\n"
        
        # Situational context
        if play_data.get('situation'):
            tweet += f"⚾ {play_data['situation']}\n"
        
        tweet += f"\n#JuanSoto #Mets #MLB #PatientHitter"
        
    elif play_data['description'].lower() == 'strikeout':
        tweet = f"❌ Juan Soto strikes out"
        
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
        
        tweet += f"\n#JuanSoto #Mets #MLB"
        
    else:
        # Generic at-bat with enhanced context
        tweet = f"⚾ Juan Soto: {play_data['description']}\n\n"
        
        # Add relevant stats if available
        if play_data.get('exit_velocity') != 'N/A':
            tweet += f"💪 Exit Velocity: {play_data['exit_velocity']} mph\n"
        if play_data.get('launch_angle') != 'N/A':
            tweet += f"📐 Launch Angle: {play_data['launch_angle']}°\n"
        
        # Season context
        if season_stats:
            tweet += f"\n📊 Season: .{season_stats.get('avg', '000')}/{season_stats.get('obp', '.000')}/{season_stats.get('slg', '.000')}\n"
        
        tweet += f"\n#JuanSoto #Mets #MLB"
    
    return tweet

def keep_alive():
    """Send a request to keep the service alive"""
    try:
        requests.get("https://soto-hr-tracker.onrender.com/")
    except:
        pass

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

def check_soto_at_bats():
    """Check for Soto's at-bats and tweet if found"""
    global last_check_time, last_check_status
    
    try:
        soto_id = get_soto_id()
        
        if TEST_MODE:
            # Generate test at-bat with enhanced data
            test_at_bat = generate_test_at_bat()
            at_bat_id = f"{test_at_bat['game_date']}_{test_at_bat['inning']}_{test_at_bat['at_bat_number']}"
            
            if at_bat_id not in processed_at_bats:
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
        else:
            # Get current game data
            game_data = get_current_game()
            
            # Get Soto's recent at-bats with enhanced data
            url = f"https://statsapi.mlb.com/api/v1/people/{soto_id}/stats"
            params = {
                "stats": "gameLog",
                "season": datetime.now().year,
                "group": "hitting"
            }
            response = requests.get(url, params=params)
            recent_at_bats = response.json()
            
            # Also get live game data if available
            live_game_url = "https://statsapi.mlb.com/api/v1/schedule"
            live_params = {
                "sportId": 1,
                "date": datetime.now().strftime("%m/%d/%Y"),
                "hydrate": "game(content(editorial(recap))),linescore,team"
            }
            live_response = requests.get(live_game_url, params=live_params)
            live_data = live_response.json()
            
            if recent_at_bats and 'stats' in recent_at_bats:
                for game in recent_at_bats['stats']:
                    if game['date'] == datetime.now().strftime("%Y-%m-%d"):
                        for at_bat in game.get('splits', []):
                            at_bat_id = f"{game['date']}_{at_bat.get('inning', 1)}_{at_bat.get('atBatIndex', 1)}"
                            
                            if at_bat_id not in processed_at_bats:
                                # Enhanced play data extraction
                                result_event = at_bat.get('result', {}).get('event', 'Unknown')
                                hit_data = at_bat.get('hitData', {})
                                pitch_data = at_bat.get('pitchData', {})
                                
                                play_data = {
                                    'type': 'home_run' if result_event == 'Home Run' else 'other',
                                    'description': result_event,
                                    'exit_velocity': hit_data.get('launchSpeed', 'N/A'),
                                    'launch_angle': hit_data.get('launchAngle', 'N/A'),
                                    'distance': hit_data.get('totalDistance', 'N/A'),
                                    'hit_distance': hit_data.get('totalDistance', 'N/A'),
                                    'xba': hit_data.get('xba', 'N/A'),
                                    'barrel_classification': 'Barrel' if hit_data.get('isBarrel') else 'Hard Hit' if hit_data.get('launchSpeed', 0) > 95 else '',
                                    'situation': get_situational_context(),  # Could be enhanced with real game situation
                                    'rbi_on_play': at_bat.get('result', {}).get('rbi', 0)
                                }
                                
                                # Add strikeout data if it's a strikeout
                                if result_event == 'Strikeout':
                                    play_data.update({
                                        'strikeout_type': 'looking' if 'called' in at_bat.get('result', {}).get('description', '').lower() else 'swinging',
                                        'pitch_type': pitch_data.get('type', 'N/A'),
                                        'pitch_speed': pitch_data.get('startSpeed', 'N/A'),
                                        'pitch_location': f"Zone {pitch_data.get('zone', 'N/A')}" if pitch_data.get('zone') else 'N/A'
                                    })
                                
                                tweet = format_tweet(play_data)
                                client.create_tweet(text=tweet)
                                logger.info(f"Tweeted: {tweet}")
                                
                                processed_at_bats.add(at_bat_id)
                                last_check_status = f"Found at-bat: {result_event} {play_data.get('situation', '')}"
            
            # Clear memory after processing
            gc.collect()
            
            if not last_check_status.startswith("Found"):
                last_check_status = "No new at-bats found"
        
        last_check_time = datetime.now()
        
    except Exception as e:
        error_msg = f"Error occurred: {str(e)}"
        logger.error(error_msg)
        last_check_status = error_msg

def background_checker():
    """Background thread to check for Soto's at-bats"""
    while True:
        check_soto_at_bats()
        time.sleep(120)  # Wait 2 minutes between checks

@app.route('/')
def home():
    """Render the home page with status information"""
    global last_check_time, last_check_status
    
    if last_check_time is None:
        status = "Initializing..."
    else:
        status = f"Last check: {last_check_time.strftime('%Y-%m-%d %H:%M:%S')} - {last_check_status}"
    
    return f"""
    <html>
        <head>
            <title>Juan Soto HR Tracker</title>
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
                <h1>Juan Soto HR Tracker</h1>
                <div class="status">
                    <p><strong>Status:</strong> {status}</p>
                    <p><strong>Mode:</strong> {'TEST' if TEST_MODE else 'PRODUCTION'}</p>
                </div>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    logger.info("Starting Juan Soto HR Tracker...")
    logger.info(f"TEST_MODE: {TEST_MODE}")
    logger.info(f"SOTO_MLB_ID: {SOTO_MLB_ID}")
    
    # Start the background checker thread
    logger.info("Starting background checker thread...")
    checker_thread = threading.Thread(target=background_checker, daemon=True)
    checker_thread.start()
    logger.info("Background checker thread started")
    
    # Start the Flask app
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}...")
    app.run(host='0.0.0.0', port=port) 