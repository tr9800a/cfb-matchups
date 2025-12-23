import json
import os
import time
import cfbd
import config
from collections import defaultdict

# --- CONFIG ---
GAMES_FILE = getattr(config, 'CACHE_FILE', 'cfb_games_cache.json')
STATS_FILE = 'season_stats.json'

def get_api_client():
    conf = cfbd.Configuration()
    client = cfbd.ApiClient(conf)
    client.default_headers['Authorization'] = f"Bearer {config.API_KEY}"
    return client

def calculate_records(games):
    """
    Scans game history to calculate (Wins, Losses, Ties) for every Team-Year.
    Returns: dict { (Team, Year): {'w': 0, 'l': 0, 't': 0} }
    """
    print(f"   Calculing W-L records from {len(games)} games...")
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
    """
    Downloads Final AP Rankings for every year.
    Returns: dict { (Team, Year): Rank }
    """
    print("   Downloading historical AP Polls...")
    client = get_api_client()
    api = cfbd.RankingsApi(client)
    
    rank_map = {} # (Team, Year) -> Rank
    
    for year in range(start_year, end_year + 1):
        print(f"      Fetching {year}...", end='\r')
        try:
            # We want the final poll. 'postseason' often works, otherwise max week.
            weeks = api.get_rankings(year=year, season_type='postseason')
            if not weeks:
                # Fallback to regular season final if postseason missing
                weeks = api.get_rankings(year=year, season_type='regular')
            
            if not weeks: continue

            # Get the very last available poll for this year
            final_week = weeks[-1]
            
            # Find the AP Top 25
            ap_poll = next((p for p in final_week.polls if p.poll == 'AP Top 25'), None)
            if not ap_poll:
                # Fallback to Coaches or whatever is there if AP missing (rare)
                if final_week.polls: ap_poll = final_week.polls[0]
            
            if ap_poll:
                for r in ap_poll.ranks:
                    rank_map[(r.school, year)] = r.rank
            
            time.sleep(0.15) # Respect rate limits
            
        except Exception as e:
            print(f"\n[WARN] Failed rankings for {year}: {e}")
            
    print(f"\n   Acquired final rankings for {len(rank_map)} team-seasons.")
    return rank_map

def main():
    print("BUILDING SEASON STATS DB...")
    
    # 1. Load Games
    if not os.path.exists(GAMES_FILE):
        print("[ERROR] No games cache. Run main.py first.")
        return
    with open(GAMES_FILE, 'r') as f:
        games = json.load(f)
        
    # 2. Calculate Win %
    records = calculate_records(games)
    
    # 3. Fetch Rankings
    # Determine year range from games
    years = [g['season'] for g in games]
    start_y, end_y = min(years), max(years)
    rankings = fetch_rankings(start_y, end_y)
    
    # 4. Merge and Save
    # Structure: Key = "Team|Year" (String key for JSON compatibility)
    final_db = {}
    
    all_keys = set(records.keys()) | set(rankings.keys())
    
    for (team, year) in all_keys:
        rec = records.get((team, year), {'w': 0, 'l': 0, 't': 0})
        rank = rankings.get((team, year), None)
        
        total_g = rec['w'] + rec['l'] + rec['t']
        win_pct = (rec['w'] / total_g) if total_g > 0 else 0.0
        
        key = f"{team}|{year}"
        final_db[key] = {
            'w': rec['w'],
            'l': rec['l'],
            't': rec['t'],
            'pct': win_pct,
            'rank': rank
        }
        
    with open(STATS_FILE, 'w') as f:
        json.dump(final_db, f)
        
    print(f"Saved stats for {len(final_db)} team-seasons to {STATS_FILE}")

if __name__ == "__main__":
    main()