import os
import time
import logging
import warnings
from datetime import datetime
import tweepy
from pybaseball import playerid_lookup, batting_stats, statcast_batter
from dotenv import load_dotenv
import requests
import random

# Suppress SyntaxWarnings from tweepy
warnings.filterwarnings("ignore", category=SyntaxWarning)

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
                            
                            # Add strikeout data if it's a strikeout
                            if at_bat['events'] == 'strikeout':
                                play_data.update({
                                    'strikeout_type': 'looking' if at_bat.get('strikeout_type', '').lower() == 'looking' else 'swinging',
                                    'pitch_type': at_bat.get('pitch_type', 'N/A'),
                                    'pitch_speed': at_bat.get('release_speed', 'N/A'),
                                    'pitch_location': f"{at_bat.get('plate_x', 'N/A')}, {at_bat.get('plate_z', 'N/A')}"
                                })
                            
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