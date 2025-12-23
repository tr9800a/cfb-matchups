import json
import os
import time
import cfbd
import config
from collections import defaultdict

# --- CONFIG ---
GAMES_FILE = getattr(config, 'CACHE_FILE', 'cfb_games_cache.json')
STATS_FILE = 'season_stats.json'

# Priority list of polls to capture (in order of prestige/relevance)
POLL_PRIORITY = [
    'AP Top 25',
    'Coaches Poll',
    'FCS Coaches Poll', 
    'STATS Perform FCS Top 25',
    'AFCA Division II Coaches Poll',
    'D3football.com Top 25'
]

def get_api_client():
    conf = cfbd.Configuration()
    client = cfbd.ApiClient(conf)
    client.default_headers['Authorization'] = f"Bearer {config.API_KEY}"
    return client

def calculate_records(games):
    print("   Calculing W-L records...")
    records = defaultdict(lambda: {'w': 0, 'l': 0, 't': 0})
    
    for g in games:
        if g.get('home_score') is None or g.get('away_score') is None: continue
        
        y = g['season']
        h, a = g['home'], g['away']
        hs, as_ = g['home_score'], g['away_score']
        
        if hs > as_:
            records[(h, y)]['w'] += 1
            records[(a, y)]['l'] += 1
        elif as_ > hs:
            records[(a, y)]['w'] += 1
            records[(h, y)]['l'] += 1
        else:
            records[(h, y)]['t'] += 1
            records[(a, y)]['t'] += 1
            
    return records

def fetch_rankings(start_year, end_year):
    print("   Downloading historical rankings (FBS, FCS, D2, D3)...")
    client = get_api_client()
    api = cfbd.RankingsApi(client)
    
    # Store (Team, Year) -> {rank, poll_name}
    rank_map = {} 
    
    for year in range(start_year, end_year + 1):
        print(f"      Fetching {year}...", end='\r')
        try:
            # We try 'postseason' first to get final rankings
            weeks = api.get_rankings(year=year, season_type='postseason')
            if not weeks:
                weeks = api.get_rankings(year=year, season_type='regular')
            
            if not weeks: continue

            # We look at the LAST available week
            final_week = weeks[-1]
            
            # Iterate through our Priority List to find the best available poll for each team
            # Note: A year might have multiple polls (e.g., AP for FBS, FCS Coaches for FCS)
            # We capture ALL of them.
            
            available_polls = {p.poll: p for p in final_week.polls}
            
            for target_poll_name in POLL_PRIORITY:
                if target_poll_name in available_polls:
                    poll_data = available_polls[target_poll_name]
                    
                    for r in poll_data.ranks:
                        key = (r.school, year)
                        # Only set if not already set by a higher priority poll
                        # (Though usually teams don't appear in multiple final polls across divisions)
                        if key not in rank_map:
                            rank_map[key] = {
                                'rank': r.rank,
                                'poll': target_poll_name
                            }

            time.sleep(0.15)
            
        except Exception as e:
            print(f"\n[WARN] Failed rankings for {year}: {e}")
            
    print(f"\n   Acquired final rankings for {len(rank_map)} team-seasons.")
    return rank_map

def main():
    print("BUILDING SEASON STATS DB...")
    
    if not os.path.exists(GAMES_FILE):
        print("[ERROR] No games cache. Run main.py first.")
        return
    with open(GAMES_FILE, 'r') as f:
        games = json.load(f)
        
    records = calculate_records(games)
    
    years = [g['season'] for g in games]
    if not years:
        print("[ERROR] No games found.")
        return
        
    start_y, end_y = min(years), max(years)
    rankings = fetch_rankings(start_y, end_y)
    
    final_db = {}
    all_keys = set(records.keys()) | set(rankings.keys())
    
    for (team, year) in all_keys:
        rec = records.get((team, year), {'w': 0, 'l': 0, 't': 0})
        rank_info = rankings.get((team, year), {'rank': None, 'poll': None})
        
        total_g = rec['w'] + rec['l'] + rec['t']
        win_pct = (rec['w'] / total_g) if total_g > 0 else 0.0
        
        key = f"{team}|{year}"
        final_db[key] = {
            'w': rec['w'],
            'l': rec['l'],
            't': rec['t'],
            'pct': win_pct,
            'rank': rank_info['rank'],
            'poll': rank_info['poll']
        }
        
    with open(STATS_FILE, 'w') as f:
        json.dump(final_db, f)
        
    print(f"DONE. Saved stats for {len(final_db)} team-seasons to {STATS_FILE}")

if __name__ == "__main__":
    main()