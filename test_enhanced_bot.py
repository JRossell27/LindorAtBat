#!/usr/bin/env python3

import sys
sys.path.append('.')
from soto_tracker import generate_test_at_bat, format_tweet, get_soto_season_stats

def main():
    print('=== ENHANCED JUAN SOTO BOT DEMO ===\n')
    print('🚀 New Features Added:')
    print('• Season stats integration (AVG/OBP/SLG/OPS)')
    print('• Advanced metrics (xBA, barrel classification)')
    print('• Situational context (runners, count, etc.)')
    print('• Enhanced pitch data for strikeouts')
    print('• Walk rate and plate discipline stats')
    print('• RBI tracking and hit distance')
    print('• Improved emoji usage and formatting\n')
    print('='*60 + '\n')

    # Generate different types of at-bats to showcase features
    at_bat_types = []
    
    # Force specific outcomes for demo
    for i in range(5):
        test_at_bat = generate_test_at_bat()
        
        play_data = {
            'type': 'home_run' if test_at_bat['events'] == 'home_run' else 'other',
            'description': test_at_bat['description'],
            'exit_velocity': test_at_bat.get('launch_speed', 'N/A'),
            'launch_angle': test_at_bat.get('launch_angle', 'N/A'),
            'distance': test_at_bat.get('hit_distance_sc', 'N/A'),
            'situation': test_at_bat.get('situation', ''),
            'barrel_classification': test_at_bat.get('barrel_classification', ''),
            'xba': test_at_bat.get('xba', 'N/A'),
            'hit_distance': test_at_bat.get('hit_distance', 'N/A'),
            'rbi_on_play': test_at_bat.get('rbi_on_play', 0)
        }
        
        if test_at_bat['events'] == 'strikeout':
            play_data.update({
                'strikeout_type': test_at_bat.get('strikeout_type', 'N/A'),
                'pitch_type': test_at_bat.get('pitch_type', 'N/A'),
                'pitch_speed': test_at_bat.get('pitch_speed', 'N/A'),
                'pitch_location': test_at_bat.get('pitch_location', 'N/A')
            })
        
        print(f'--- Example Tweet #{i+1}: {test_at_bat["description"].upper()} ---')
        tweet = format_tweet(play_data)
        print(tweet)
        print('\n' + '='*60 + '\n')

if __name__ == "__main__":
    main() 