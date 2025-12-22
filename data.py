import os
import json
import time
import cfbd
import config
import csv
from datetime import datetime

TEAMS_CACHE_FILE = config.TEAMS_CACHE_FILE
GAMES_CACHE_FILE = config.CACHE_FILE
MEMBERSHIP_FILE = config.MEMBERSHIP_FILE
LINEAGE_FILE = config.LINEAGE_FILE

def get_api_client():
    conf = cfbd.Configuration()
    client = cfbd.ApiClient(conf)
    client.default_headers['Authorization'] = f"Bearer {config.API_KEY}"
    return client

def load_games_data():
    if os.path.exists(GAMES_CACHE_FILE):
        with open(GAMES_CACHE_FILE, 'r') as f:
            return json.load(f)

    print("[INFO] No games cache found. Downloading full history...")
    client = get_api_client()
    api = cfbd.GamesApi(client)

    all_games = []
    # Note: Using config years
    for year in range(config.START_YEAR, config.END_YEAR):
        print(f"   Fetching games for {year}...", end='\r')
        try:
            games = api.get_games(year=year)
            for g in games:
                if (g.home_team and g.away_team and 
                    g.home_points is not None and g.away_points is not None):
                    all_games.append({
                        'season': g.season,
                        'date': str(g.start_date),
                        'home': g.home_team,
                        'away': g.away_team,
                        'home_score': g.home_points,
                        'away_score': g.away_points
                    })
            time.sleep(0.1)
        except Exception as e:
            print(f"\n[WARN] Failed to fetch {year}: {e}")
    
    with open(GAMES_CACHE_FILE, 'w') as f:
        json.dump(all_games, f)
    return all_games

def load_teams_data():
    """
    Downloads and caches the full list of teams (FBS, FCS, D2, D3).
    This is required for the --div filters to work.
    """
    if os.path.exists(TEAMS_CACHE_FILE):
        with open(TEAMS_CACHE_FILE, 'r') as f:
            return json.load(f)
            
    print("[INFO] No teams cache found. Downloading full Team Database...")
    client = get_api_client()
    api = cfbd.TeamsApi(client)
    
    try:
        # get_teams() fetches all teams (FBS, FCS, D2, D3)
        teams = api.get_teams()
        
        teams_data = []
        for t in teams:
            teams_data.append({
                'school': t.school,
                'conference': t.conference,
                'classification': t.classification, # fbs, fcs, ii, iii
                'division': t.division
            })
            
        with open(TEAMS_CACHE_FILE, 'w') as f:
            json.dump(teams_data, f)
            
        print(f"[SUCCESS] Cached {len(teams_data)} teams.")
        return teams_data
        
    except Exception as e:
        print(f"[ERROR] Failed to download teams: {e}")
        return []

def load_lineage_data():
    """Loads the conference aliases and lineage JSON."""
    if not os.path.exists(LINEAGE_FILE):
        print(f"[WARN] Lineage file '{LINEAGE_FILE}' not found. Using empty map.")
        return {}
    with open(LINEAGE_FILE, 'r') as f:
        return json.load(f)

def load_membership_data():
    """Loads the historical membership CSV."""
    membership = []
    if not os.path.exists(MEMBERSHIP_FILE):
        print(f"[WARN] Membership file '{MEMBERSHIP_FILE}' not found.")
        return []
        
    with open(MEMBERSHIP_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Normalize keys
                clean_row = {k.strip().lower(): v.strip() for k, v in row.items()}
                
                team = clean_row.get('school') or clean_row.get('team')
                conf = clean_row.get('conference')
                
                start_raw = clean_row.get('start_year') or clean_row.get('start year')
                end_raw = clean_row.get('end_year') or clean_row.get('end year')
                
                start_year = int(start_raw) if start_raw else 1869
                end_year = int(end_raw) if end_raw else 9999
                
                membership.append({
                    'team': team,
                    'conference': conf,
                    'start': start_year,
                    'end': end_year
                })
            except ValueError:
                continue 
    return membership

# --- SMART LOOKUP ENGINE ---

def resolve_conference_name(user_input, lineage_data):
    if not user_input: return None
    raw = user_input.strip()
    
    if raw in lineage_data:
        return raw
        
    for official, info in lineage_data.items():
        aliases = []
        if isinstance(info, list): aliases = info
        elif isinstance(info, dict): aliases = info.get('aliases', []) + info.get('lineage', [])
        
        if raw.lower() == official.lower():
            return official
        for alias in aliases:
            if raw.lower() == alias.lower():
                return official
                
    return raw 

def get_teams_in_conference_range(conf_input, start_year, end_year):
    lineage = load_lineage_data()
    membership = load_membership_data()
    
    target_conf = resolve_conference_name(conf_input, lineage)
    print(f"[INFO] Resolving '{conf_input}' -> '{target_conf}' for range {start_year}-{end_year}")

    found_teams = set()
    
    for entry in membership:
        entry_conf = entry['conference']
        is_match = (entry_conf.lower() == target_conf.lower())
        
        if is_match:
            # Check overlap
            if (entry['start'] <= end_year) and (start_year <= entry['end']):
                found_teams.add(entry['team'])
                
    if not found_teams:
        print(f"[WARN] No historical members found for '{target_conf}' between {start_year}-{end_year}.")
        
    return found_teams

def get_team_filter(divisions):
    # This was the function causing the error because load_teams_data was missing
    all_teams = load_teams_data()
    
    if not divisions or 'all' in divisions:
        return None
        
    valid_set = set()
    divisions_lower = [d.lower() for d in divisions]
    
    for t in all_teams:
        if t.get('classification') and t['classification'].lower() in divisions_lower:
            valid_set.add(t['school'])
            
    return valid_set