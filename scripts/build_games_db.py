import cfbd
import json
import time
import sys
import os
from tqdm import tqdm
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

CACHE_FILE = 'data/cfb_games_cache.json'

def get_api_client():
    """
    Manually builds the API client with the Bearer token in the default headers.
    """
    conf = cfbd.Configuration()
    client = cfbd.ApiClient(conf)
    client.default_headers['Authorization'] = f"Bearer {config.API_KEY}"
    return client

def build_games_cache(start_year=1869, end_year=2025):
    # Initialize the API instance using the custom client builder
    api_client = get_api_client()
    api_instance = cfbd.GamesApi(api_client)
    
    all_games = []
    
    print(f"Fetching games history from {start_year} to {end_year}...")
    
    # tqdm creates a progress bar for the loop
    for year in tqdm(range(start_year, end_year + 1)):
        try:
            # Fetch regular and postseason
            games_reg = api_instance.get_games(year=year, season_type='regular')
            games_post = api_instance.get_games(year=year, season_type='postseason')
            
            yearly_games = games_reg + games_post
            
            for game in yearly_games:
                # Convert the game object to a dictionary manually to control field naming
                # and handle specific field extractions safely.
                game_record = {
                    "id": getattr(game, 'id', None),
                    "season": getattr(game, 'season', None),
                    "week": getattr(game, 'week', None),
                    "season_type": getattr(game, 'season_type', None),
                    "start_date": getattr(game, 'start_date', None),
                    "neutral_site": getattr(game, 'neutral_site', None),
                    "conference_game": getattr(game, 'conference_game', None),
                    "attendance": getattr(game, 'attendance', None),
                    "venue_id": getattr(game, 'venue_id', None),
                    "venue": getattr(game, 'venue', None),
                    "home_team": getattr(game, 'home_team', None),
                    "home_conference": getattr(game, 'home_conference', None),
                    "home_points": getattr(game, 'home_points', None),
                    "home_line_scores": getattr(game, 'home_line_scores', None),
                    "home_post_win_prob": getattr(game, 'home_post_win_prob', None),
                    "away_team": getattr(game, 'away_team', None),
                    "away_conference": getattr(game, 'away_conference', None),
                    "away_points": getattr(game, 'away_points', None),
                    "away_line_scores": getattr(game, 'away_line_scores', None),
                    "away_post_win_prob": getattr(game, 'away_post_win_prob', None),
                    "excitement_index": getattr(game, 'excitement_index', None),
                    "highlights": getattr(game, 'highlights', None),
                    "notes": getattr(game, 'notes', None),
                    "home_classification": getattr(game, 'home_classification', None),
                    "away_classification": getattr(game, 'away_classification', None)
                }
                
                all_games.append(game_record)
                
        except Exception as e:
            print(f"Error fetching data for {year}: {e}")
            continue

        # Respect rate limits
        time.sleep(0.1)

    print(f"Saving {len(all_games)} games to {CACHE_FILE}...")
    
    # Write to file
    with open(CACHE_FILE, 'w') as f:
        # default=str fixes the "TypeError: Object of type datetime..."
        json.dump(all_games, f, indent=4, default=str) 

    print("Done.")

if __name__ == "__main__":
    build_games_cache()