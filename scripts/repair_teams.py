import json
import os
import sys
from collections import Counter
from tqdm import tqdm

# Ensure we can find the config file
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

TEAMS_FILE = 'data/cfb_teams_cache.json'
GAMES_FILE = 'data/cfb_games_cache.json'

def repair_teams():
    print(f"Loading data...")
    
    if not os.path.exists(TEAMS_FILE) or not os.path.exists(GAMES_FILE):
        print("Error: Cache files not found.")
        return

    with open(TEAMS_FILE, 'r') as f:
        teams = json.load(f)
        
    with open(GAMES_FILE, 'r') as f:
        games = json.load(f)

    # 1. Build a Lookup Table from Game Data
    # Map Team Name -> List of (Conference, Classification, Season)
    print("Analyzing game history to infer team details...")
    team_history = {}
    
    for g in tqdm(games):
        year = g['season']
        
        # We prioritize recent data (2022-2025)
        if year < 2022: continue
        
        # Check Home Team
        h_team = g.get('home_team')
        h_conf = g.get('home_conference')
        h_class = g.get('home_classification') # Note: might be 'home_division' in older cache versions
        
        if h_team and h_conf:
            if h_team not in team_history: team_history[h_team] = []
            team_history[h_team].append({'conf': h_conf, 'class': h_class, 'year': year})
            
        # Check Away Team
        a_team = g.get('away_team')
        a_conf = g.get('away_conference')
        a_class = g.get('away_classification')
        
        if a_team and a_conf:
            if a_team not in team_history: team_history[a_team] = []
            team_history[a_team].append({'conf': a_conf, 'class': a_class, 'year': year})

    # 2. Update Teams Cache
    print("Updating teams cache...")
    updated_count = 0
    
    for t in teams:
        name = t['school']
        
        # If this team exists in our game history
        if name in team_history:
            history = team_history[name]
            
            # Sort by year (descending) to get most recent info
            history.sort(key=lambda x: x['year'], reverse=True)
            
            latest_entry = history[0]
            recent_conf = latest_entry['conf']
            recent_class = latest_entry['class']
            
            # UPDATE LOGIC:
            # If current data is missing (None) or seems generic ("Unknown"), overwrite it.
            # You can force overwrite by removing the 'if' checks below.
            
            changes_made = False
            
            # Fix Conference
            if t.get('conference') is None or t.get('conference') == 'Unknown':
                t['conference'] = recent_conf
                changes_made = True
                
            # Fix Classification
            # The API sometimes uses 'fbs', 'fcs', 'ii', 'iii'
            if t.get('classification') is None or t.get('classification') == 'unknown':
                t['classification'] = recent_class
                changes_made = True
                
            if changes_made:
                updated_count += 1

    # 3. Save
    print(f"Repaired {updated_count} teams.")
    with open(TEAMS_FILE, 'w') as f:
        json.dump(teams, f, indent=4)
    print("Done.")

if __name__ == "__main__":
    repair_teams()