import os
import json
import time
import cfbd
import config
import csv
import pandas as pd
import re
from datetime import datetime

# --- FILE PATHS ---
TEAMS_CACHE_FILE = config.TEAMS_CACHE_FILE
GAMES_CACHE_FILE = config.GAMES_FILE
MEMBERSHIP_FILE = config.MEMBERSHIP_FILE
LINEAGE_FILE = config.LINEAGE_FILE
STATS_FILE = config.STATS_FILE

def get_api_client():
    conf = cfbd.Configuration()
    client = cfbd.ApiClient(conf)
    client.default_headers['Authorization'] = f"Bearer {config.API_KEY}"
    return client

def load_games_data():
    if os.path.exists(GAMES_CACHE_FILE):
        with open(GAMES_CACHE_FILE, 'r') as f:
            games = json.load(f)

            # --- COMPATIBILITY PATCH ---
            # The database now uses 'home_classification', 'home_team', etc.
            # But older analysis scripts (stats_sor, etc.) expect 'home_division', 'home'.
            # We map them here so we don't have to rewrite every script.
            for g in games:
                # 1. Restore 'home' and 'away' team names
                if 'home_team' in g and 'home' not in g:
                    g['home'] = g['home_team']
                if 'away_team' in g and 'away' not in g:
                    g['away'] = g['away_team']
                
                # 2. Map classification -> division
                if 'home_classification' in g:
                    g['home_division'] = g['home_classification']
                elif 'home_division' not in g:
                    g['home_division'] = None

                if 'away_classification' in g:
                    g['away_division'] = g['away_classification']
                elif 'away_division' not in g:
                    g['away_division'] = None
                    
                # 3. Map points -> score
                if 'home_points' in g and 'home_score' not in g:
                    g['home_score'] = g['home_points']
                if 'away_points' in g and 'away_score' not in g:
                    g['away_score'] = g['away_points']
            
            return games
    return [] 

def load_lineage_data():
    if not os.path.exists(LINEAGE_FILE): return {}
    with open(LINEAGE_FILE, 'r') as f:
        return json.load(f)

def load_season_stats():
    """Loads the Win/Loss/Rank database."""
    if not os.path.exists(STATS_FILE):
        return {}
    with open(STATS_FILE, 'r') as f:
        return json.load(f)

def get_team_stats(team, year, stats_db):
    """Helper to safely get stats for a specific team-year"""
    key = f"{team}|{year}"
    return stats_db.get(key, {'w': 0, 'l': 0, 't': 0, 'pct': 0.0, 'rank': None})

# --- NORMALIZATION ---
def normalize_conf_name(name):
    """
    Aggressively normalizes conference names to a common ID.
    1. Lowercase
    2. Replace number-words with digits (eight -> 8) ANYWHERE in string
    3. Remove all non-alphanumeric characters
    """
    if not isinstance(name, str): return ""
    s = name.lower()
    
    replacements = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'eleven': '11', 'twelve': '12'
    }
    for word, digit in replacements.items():
        s = s.replace(word, digit)
        
    s = "".join(c for c in s if c.isalnum())
    return s

def load_membership_data():
    if not os.path.exists(MEMBERSHIP_FILE): return pd.DataFrame()
    try:
        df = pd.read_csv(MEMBERSHIP_FILE)
        df.columns = [c.strip().lower() for c in df.columns]
        # Pre-compute normalized names for speed
        df['norm_name'] = df['conference_name'].apply(normalize_conf_name)
        return df
    except Exception:
        return pd.DataFrame()

def load_teams_data():
    if os.path.exists(TEAMS_CACHE_FILE):
        with open(TEAMS_CACHE_FILE, 'r') as f:
            return json.load(f)
    return []

# --- SMART LOOKUP ENGINE ---

def resolve_conference_key(user_input, lineage_data):
    if not user_input: return None
    target_norm = normalize_conf_name(user_input)
    conferences = lineage_data.get('conferences', {})
    
    # Check Keys
    for key in conferences:
        if normalize_conf_name(key) == target_norm:
            return key
            
    # Check Aliases
    for key, info in conferences.items():
        for alias in info.get('aliases', []):
            name = alias.get('name', '') if isinstance(alias, dict) else str(alias)
            if normalize_conf_name(name) == target_norm:
                return key
                
    return user_input

def get_teams_in_conference_range(conf_input, start_year, end_year):
    lineage_data = load_lineage_data()
    df = load_membership_data()
    
    if df.empty:
        print("[WARN] Membership DB empty. Please run build_membership_db.py")
        return set()

    # 1. Pseudo-Conference / Division Support
    norm_input = normalize_conf_name(conf_input)
    div_map = {'fbs': 'fbs', 'fcs': 'fcs', 'd2': 'ii', 'ii': 'ii', 'd3': 'iii', 'iii': 'iii'}
    
    if norm_input in div_map:
        target_class = div_map[norm_input]
        print(f"[INFO] Detected Division Filter: '{target_class.upper()}'")
        all_teams = load_teams_data()
        class_teams = set()
        for t in all_teams:
            if t.get('classification') and t['classification'].lower() == target_class:
                class_teams.add(t['school'])
        
        # Only return teams active in the DB for the requested years
        mask_year = (df['year'] >= start_year) & (df['year'] <= end_year)
        active_teams = set(df[mask_year]['school'].unique())
        return class_teams.intersection(active_teams)

    # 2. Lineage Lookup
    official_key = resolve_conference_key(conf_input, lineage_data)
    print(f"[INFO] Resolving '{conf_input}' -> '{official_key}'")
    
    found_teams = set()
    conf_config = lineage_data.get('conferences', {}).get(official_key, {})
    predecessors = conf_config.get('predecessors', [])
    target_norm = normalize_conf_name(official_key)
    
    for year in range(start_year, end_year + 1):
        # A. Direct Membership
        mask_year = (df['year'] == year)
        mask_direct = (df['norm_name'] == target_norm)
        found_teams.update(df[mask_year & mask_direct]['school'].unique())
        
        # B. Lineage Membership (Predecessors)
        for pred in predecessors:
            if year < pred['end_year']:
                pred_norm = normalize_conf_name(pred['name'])
                mask_pred = (df['norm_name'] == pred_norm)
                candidates = set(df[mask_year & mask_pred]['school'].unique())
                
                # C. Filters (Partial Merge Logic)
                if 'filter_teams' in pred and pred['filter_teams']:
                    allowed = set(pred['filter_teams'])
                    found_teams.update({t for t in candidates if t in allowed})
                else:
                    found_teams.update(candidates)

    if not found_teams:
        print(f"[WARN] No members found for '{official_key}' (or ancestors) in {start_year}-{end_year}.")
        
    return found_teams
    
def get_team_filter(divisions):
    all_teams = load_teams_data()
    if not divisions or 'all' in divisions: return None
    valid_set = set()
    divisions_lower = [d.lower() for d in divisions]
    for t in all_teams:
        if t.get('classification') and t['classification'].lower() in divisions_lower:
            valid_set.add(t['school'])
    return valid_set

def get_team_classification(team_name):
    """
    Returns the classification (fbs, fcs, ii, iii) for a team.
    Relies on the most recent data in the cache.
    """
    # Load cache (you might want to store this in a global variable to avoid re-loading)
    teams = load_teams_data()
    
    # Simple normalization for lookup
    target = team_name.lower().strip()
    
    for t in teams:
        if t['school'].lower().strip() == target:
            cls = t.get('classification')
            return cls.lower() if cls else 'unknown'
            
    return 'unknown'