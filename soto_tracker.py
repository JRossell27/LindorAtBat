import os
import time
import logging
from datetime import datetime
import struct
import imghdr
import tweepy
from pybaseball import playerid_lookup, batting_stats, statcast_batter
from dotenv import load_dotenv
import requests
import random

# Custom imghdr implementation for Python 3.11+
def what(file, h=None):
    if h is None:
        if isinstance(file, str):
            f = open(file, 'rb')
            h = f.read(32)
            f.close()
        else:
            location = file.tell()
            h = file.read(32)
            file.seek(location)
    if h.startswith(b'\xff\xd8'):
        return 'jpeg'
    if h.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if h.startswith(b'GIF87a') or h.startswith(b'GIF89a'):
        return 'gif'
    if h.startswith(b'BM'):
        return 'bmp'
    return None

# Monkey patch imghdr.what
imghdr.what = what

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

def get_soto_id():
    """Get Juan Soto's MLB ID"""
    soto_id = playerid_lookup('soto', 'juan')
    return soto_id['key_mlbam'].iloc[0]

def get_current_game():
    """Get the current game ID if Soto is playing"""
    # This is a simplified version - you might want to enhance this
    # to check if the Mets are playing and if Soto is in the lineup
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": datetime.now().strftime("%m/%d/%Y")
    }
    response = requests.get(url, params=params)
    return response.json()

def format_tweet(play_data):
    """Format the tweet based on the play data"""
    if play_data['type'] == 'home_run':
        tweet = f"🚨 JUAN SOTO HOME RUN! 🚨\n\n"
        tweet += f"Exit Velocity: {play_data['exit_velocity']} mph\n"
        tweet += f"Distance: {play_data['distance']} ft\n"
        tweet += f"Launch Angle: {play_data['launch_angle']}°\n"
        tweet += f"Parks: {play_data['parks']} parks\n"
        tweet += f"Season HR #{play_data['hr_number']}"
    else:
        tweet = f"Juan Soto's at-bat result:\n"
        tweet += f"Result: {play_data['description']}\n"
        if 'exit_velocity' in play_data:
            tweet += f"Exit Velocity: {play_data['exit_velocity']} mph\n"
        if 'launch_angle' in play_data:
            tweet += f"Launch Angle: {play_data['launch_angle']}°"
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
        return {
            'events': random.choice(outcomes).lower(),
            'description': random.choice(outcomes),
            'launch_speed': round(random.uniform(60, 110), 1),
            'launch_angle': round(random.uniform(-10, 45), 1),
            'game_date': datetime.now().strftime("%Y-%m-%d"),
            'inning': random.randint(1, 9),
            'at_bat_number': random.randint(1, 5)
        }

def main():
    soto_id = get_soto_id()
    logger.info(f"Starting to track Juan Soto (ID: {soto_id})")
    logger.info(f"Running in {'TEST' if TEST_MODE else 'PRODUCTION'} mode")
    
    while True:
        try:
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
                    
                    tweet = format_tweet(play_data)
                    if TEST_MODE:
                        logger.info(f"TEST MODE - Would tweet: {tweet}")
                    else:
                        client.create_tweet(text=tweet)
                        logger.info(f"Tweeted: {tweet}")
                    
                    processed_at_bats.add(at_bat_id)
            else:
                # Get current game data
                game_data = get_current_game()
                
                # Get Soto's recent at-bats
                recent_at_bats = statcast_batter(
                    start_dt=datetime.now().strftime("%Y-%m-%d"),
                    end_dt=datetime.now().strftime("%Y-%m-%d"),
                    player_id=soto_id
                )
                
                if recent_at_bats is not None and not recent_at_bats.empty:
                    for _, at_bat in recent_at_bats.iterrows():
                        at_bat_id = f"{at_bat['game_date']}_{at_bat['inning']}_{at_bat['at_bat_number']}"
                        
                        if at_bat_id not in processed_at_bats:
                            play_data = {
                                'type': 'home_run' if at_bat['events'] == 'home_run' else 'other',
                                'description': at_bat['description'],
                                'exit_velocity': at_bat.get('launch_speed', 'N/A'),
                                'launch_angle': at_bat.get('launch_angle', 'N/A'),
                                'distance': at_bat.get('hit_distance_sc', 'N/A'),
                                'parks': at_bat.get('barrel', 'N/A'),
                                'hr_number': at_bat.get('home_run', 0)
                            }
                            
                            tweet = format_tweet(play_data)
                            client.create_tweet(text=tweet)
                            logger.info(f"Tweeted: {tweet}")
                            
                            processed_at_bats.add(at_bat_id)
            
            # Keep the service alive
            keep_alive()
            
            # Wait before checking again
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            time.sleep(60)  # Wait longer if there's an error

if __name__ == "__main__":
    main() 