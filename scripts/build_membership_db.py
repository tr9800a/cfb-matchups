import json
import csv
import os
import re
import config

# --- CONFIG ---
GAMES_FILE = config.GAMES_FILE
LINEAGE_FILE = config.LINEAGE_FILE
OUTPUT_FILE = config.MEMBERSHIP_FILE

def load_json(filepath):
    if not os.path.exists(filepath):
        print(f"[ERROR] Could not find {filepath}")
        return {}
    with open(filepath, 'r') as f:
        return json.load(f)

def normalize_conf_name(name):
    if not isinstance(name, str): return None
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

def build_resolver_map(lineage_data):
    resolver = {}
    conferences = lineage_data.get('conferences', {})
    for official_name, info in conferences.items():
        resolver[normalize_conf_name(official_name)] = official_name
        for alias in info.get('aliases', []):
            name = alias.get('name', '') if isinstance(alias, dict) else str(alias)
            resolver[normalize_conf_name(name)] = official_name
    return resolver

def resolve(name, resolver):
    # 1. Normalize input
    norm = normalize_conf_name(name)
    if not norm: return "Independent" # Default to Independent if name is None/Empty
    
    # 2. Try Resolve
    if norm in resolver:
        return resolver[norm]
    
    # 3. Handle "Independent" variations explicitly
    if "independent" in norm:
        return "Independent"
        
    return name # Return original if unknown (e.g. "SIAA")

def main():
    print("STARTING MEMBERSHIP BUILDER...")
    
    games = load_json(GAMES_FILE)
    lineage = load_json(LINEAGE_FILE)
    
    if not games:
        print("No game data found.")
        return

    print(f"   Loading aliases from {LINEAGE_FILE}...")
    resolver = build_resolver_map(lineage)
    
    membership_map = {}
    
    for g in games:
        season = g['season']
        
        # PROCESS HOME
        if g.get('home'):
            h_team = g['home']
            # Default to 'Independent' if conf is None
            raw_conf = g.get('home_conf')
            h_conf = resolve(raw_conf, resolver)
            membership_map[(h_team, season)] = h_conf
            
        # PROCESS AWAY
        if g.get('away'):
            a_team = g['away']
            raw_conf = g.get('away_conf')
            a_conf = resolve(raw_conf, resolver)
            membership_map[(a_team, season)] = a_conf

    print(f"   Found {len(membership_map)} unique Team-Year records.")
    print(f"   Writing to {OUTPUT_FILE}...")
    
    sorted_records = sorted(membership_map.items(), key=lambda x: (x[0][1], x[0][0]))
    
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['school', 'year', 'conference_name', 'lineage_conference_name'])
        for (team, year), conf in sorted_records:
            writer.writerow([team, year, conf, conf])
            
    print("Database updated (Nulls -> Independent).")

if __name__ == "__main__":
    main()