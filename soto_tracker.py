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
from pybaseball import playerid_lookup, statcast_batter

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
TEST_MODE = False  # Set to False for production

# Twitter API setup
if not TEST_MODE:
    client = tweepy.Client(
        consumer_key=os.getenv('TWITTER_API_KEY'),
        consumer_secret=os.getenv('TWITTER_API_SECRET'),
        access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
        access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET'),
        bearer_token=os.getenv('TWITTER_BEARER_TOKEN')
    )

# Keep track of processed at-bats
processed_at_bats = set()

# Track last check time and status
last_check_time = None
last_check_status = "Initializing..."

def get_soto_id():
    """Get Juan Soto's MLB ID using pybaseball"""
    soto = playerid_lookup('soto', 'juan')
    if not soto.empty:
        return soto.iloc[0]['key_mlbam']
    return None

def get_current_game():
    """Get the current game ID if Soto is playing"""
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": datetime.now().strftime("%m/%d/%Y")
    }
    response = requests.get(url, params=params)
    return response.json()

def get_statcast_data(soto_id, date):
    """Get Statcast data for Soto's at-bats using pybaseball"""
    try:
        # Get today's date in YYYY-MM-DD format
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get Statcast data for today
        data = statcast_batter(today, today, soto_id)
        
        if data is not None and not data.empty:
            return data
        return None
    except Exception as e:
        logger.error(f"Error getting Statcast data: {str(e)}")
        return None

def get_soto_stats():
    """Get Soto's stats for the current season"""
    soto_id = get_soto_id()
    if not soto_id:
        return None
    
    url = f"https://statsapi.mlb.com/api/v1/people/{soto_id}/stats"
    params = {
        "stats": "season",
        "season": datetime.now().year,
        "group": "hitting"
    }
    response = requests.get(url, params=params)
    return response.json()

def format_tweet(play_data):
    """Format the tweet based on the play data"""
    if play_data['type'] == 'home_run':
        # Add emojis and formatting for home runs
        tweet = f"🚨 JUAN SOTO HOME RUN! 🚨\n\n"
        tweet += f"💪 Exit Velocity: {play_data['exit_velocity']} mph\n"
        tweet += f"📏 Distance: {play_data['distance']} ft\n"
        tweet += f"📐 Launch Angle: {play_data['launch_angle']}°\n"
        tweet += f"🏟️ Parks: {play_data['parks']} parks\n"
        tweet += f"🔢 Season HR #{play_data['hr_number']}\n\n"
        tweet += f"#JuanSoto #Mets #MLB"
    else:
        # Format based on the type of at-bat
        if play_data['description'].lower() in ['single', 'double', 'triple']:
            tweet = f"💫 Juan Soto with a {play_data['description'].upper()}!\n\n"
        elif play_data['description'].lower() == 'walk':
            tweet = f"👀 Juan Soto draws a WALK!\n\n"
        elif play_data['description'].lower() == 'strikeout':
            tweet = f"❌ Juan Soto strikes out"
            
            # Add strikeout type if available
            if 'strikeout_type' in play_data:
                if play_data['strikeout_type'] == 'looking':
                    tweet += " looking"
                elif play_data['strikeout_type'] == 'swinging':
                    tweet += " swinging"
            
            tweet += "\n\n"
            
            # Add pitch data if available
            if 'pitch_type' in play_data and play_data['pitch_type'] != 'N/A':
                tweet += f"🎯 Final Pitch: {play_data['pitch_type']}\n"
            if 'pitch_speed' in play_data and play_data['pitch_speed'] != 'N/A':
                tweet += f"⚡ Speed: {play_data['pitch_speed']} mph\n"
            if 'pitch_location' in play_data and play_data['pitch_location'] != 'N/A':
                tweet += f"📍 Location: {play_data['pitch_location']}\n"
            
        else:
            tweet = f"⚾ Juan Soto's at-bat result: {play_data['description']}\n\n"
        
        # Add relevant stats if available
        if 'exit_velocity' in play_data and play_data['exit_velocity'] != 'N/A':
            tweet += f"💪 Exit Velocity: {play_data['exit_velocity']} mph\n"
        if 'launch_angle' in play_data and play_data['launch_angle'] != 'N/A':
            tweet += f"📐 Launch Angle: {play_data['launch_angle']}°\n"
        
        tweet += f"\n#JuanSoto #Mets #MLB"
    
    return tweet

def keep_alive():
    """Send a request to keep the service alive"""
    try:
        requests.get("https://soto-hr-tracker.onrender.com/")
    except:
        pass

def generate_test_at_bat():
    """Generate a test at-bat with random data"""
    is_home_run = random.random() < 0.3  # 30% chance of home run
    
    if is_home_run:
        return {
            'events': 'home_run',
            'description': 'Home Run',
            'launch_speed': round(random.uniform(95, 115), 1),
            'launch_angle': round(random.uniform(20, 35), 1),
            'hit_distance_sc': round(random.uniform(350, 450)),
            'barrel': random.randint(20, 30),
            'home_run': random.randint(1, 30),
            'game_date': datetime.now().strftime("%Y-%m-%d"),
            'inning': random.randint(1, 9),
            'at_bat_number': random.randint(1, 5)
        }
    else:
        outcomes = ['Single', 'Double', 'Triple', 'Strikeout', 'Walk', 'Groundout', 'Flyout']
        outcome = random.choice(outcomes)
        result = {
            'events': outcome.lower(),
            'description': outcome,
            'launch_speed': round(random.uniform(60, 110), 1),
            'launch_angle': round(random.uniform(-10, 45), 1),
            'game_date': datetime.now().strftime("%Y-%m-%d"),
            'inning': random.randint(1, 9),
            'at_bat_number': random.randint(1, 5)
        }
        
        # Add strikeout-specific data
        if outcome == 'Strikeout':
            result['strikeout_type'] = random.choice(['looking', 'swinging'])
            result['pitch_type'] = random.choice(['4-Seam Fastball', 'Slider', 'Curveball', 'Changeup', 'Cutter'])
            result['pitch_speed'] = round(random.uniform(85, 98), 1)
            result['pitch_location'] = random.choice(['High and Inside', 'Low and Away', 'Middle-In', 'Middle-Out', 'High and Away'])
        
        return result

def check_soto_at_bats():
    """Check for Soto's at-bats and tweet if found"""
    global last_check_time, last_check_status
    
    try:
        soto_id = get_soto_id()
        
        if TEST_MODE:
            # Generate test at-bat
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
                    'hr_number': test_at_bat.get('home_run', 0)
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
                last_check_status = f"Found test at-bat: {test_at_bat['description']}"
        else:
            # Get current game data
            game_data = get_current_game()
            
            # Get Soto's recent at-bats
            url = f"https://statsapi.mlb.com/api/v1/people/{soto_id}/stats"
            params = {
                "stats": "gameLog",
                "season": datetime.now().year,
                "group": "hitting"
            }
            response = requests.get(url, params=params)
            recent_at_bats = response.json()
            
            if recent_at_bats and 'stats' in recent_at_bats:
                for game in recent_at_bats['stats']:
                    if game['date'] == datetime.now().strftime("%Y-%m-%d"):
                        for at_bat in game.get('splits', []):
                            at_bat_id = f"{game['date']}_{at_bat.get('inning', 1)}_{at_bat.get('atBatIndex', 1)}"
                            
                            if at_bat_id not in processed_at_bats:
                                play_data = {
                                    'type': 'home_run' if at_bat.get('result', {}).get('event') == 'Home Run' else 'other',
                                    'description': at_bat.get('result', {}).get('event', 'Unknown'),
                                    'exit_velocity': at_bat.get('hitData', {}).get('launchSpeed', 'N/A'),
                                    'launch_angle': at_bat.get('hitData', {}).get('launchAngle', 'N/A'),
                                    'distance': at_bat.get('hitData', {}).get('totalDistance', 'N/A'),
                                    'parks': at_bat.get('hitData', {}).get('barrel', 'N/A'),
                                    'hr_number': at_bat.get('seasonStats', {}).get('homeRuns', 0)
                                }
                                
                                # Add strikeout data if it's a strikeout
                                if at_bat.get('result', {}).get('event') == 'Strikeout':
                                    play_data.update({
                                        'strikeout_type': 'looking' if at_bat.get('result', {}).get('description', '').lower().startswith('called') else 'swinging',
                                        'pitch_type': at_bat.get('pitchData', {}).get('type', 'N/A'),
                                        'pitch_speed': at_bat.get('pitchData', {}).get('startSpeed', 'N/A'),
                                        'pitch_location': f"{at_bat.get('pitchData', {}).get('x', 'N/A')}, {at_bat.get('pitchData', {}).get('z', 'N/A')}"
                                    })
                                
                                tweet = format_tweet(play_data)
                                client.create_tweet(text=tweet)
                                logger.info(f"Tweeted: {tweet}")
                                
                                processed_at_bats.add(at_bat_id)
                                last_check_status = f"Found at-bat: {play_data['description']}"
            
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
    # Start the background checker thread
    checker_thread = threading.Thread(target=background_checker, daemon=True)
    checker_thread.start()
    
    # Start the Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 