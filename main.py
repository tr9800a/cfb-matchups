import warnings
import argparse
import sys
import networkx as nx
from datetime import datetime

# Suppress SSL Warnings
warnings.filterwarnings("ignore", module="urllib3")
import urllib3

import data
import graph
import utils

# ==========================================
# 1. STRENGTH OF SCHEDULE (SOS) FUNCTIONS
# ==========================================

def calculate_sos(G, team, start_year, end_year, non_conf_only, stats_db):
    """
    Calculates the WEIGHTED Opponent Win % for a specific team.
    Weights: FBS=1.0, FCS=0.6, D2=0.4, D3=0.2
    """
    if not G.has_node(team): 
        return None

    opponents_faced = []
    
    # Division Weights
    weights = {
        'fbs': 1.0,
        'fcs': 0.6,
        'ii': 0.4,
        'iii': 0.2,
        'unknown': 0.5
    }
    
    for nbr in G.neighbors(team):
        history = G.get_edge_data(team, nbr)['history']
        
        for g in history:
            year = g['season']
            if year < start_year or year > end_year: 
                continue
            
            # Non-Conference Filter Logic
            if non_conf_only:
                h_conf = g.get('home_conf')
                a_conf = g.get('away_conf')
                if h_conf and a_conf:
                    # Treat Independent vs Independent as a "Conference Game" (peer group)
                    if data.normalize_conf_name(h_conf) == data.normalize_conf_name(a_conf):
                        continue

            # Retrieve Stats
            raw_stats = data.get_team_stats(nbr, year, stats_db)
            
            # Determine Weight
            div = data.get_team_classification(nbr)
            wgt = weights.get(div, 0.5)
            
            opponents_faced.append({
                'name': nbr,
                'year': year,
                'raw': raw_stats,
                'weight': wgt,
                'div': div
            })

    if not opponents_faced: 
        return None

    # Calculate Weighted Average
    # Formula: Sum(Opp_Win_Pct * Weight) / Count
    weighted_sum = 0
    valid_games = 0
    
    for o in opponents_faced:
        rec = o['raw']
        total_g = rec['w'] + rec['l'] + rec['t']
        
        if total_g > 0:
            raw_pct = rec['w'] / total_g
            weighted_pct = raw_pct * o['weight']
            weighted_sum += weighted_pct
            valid_games += 1
            
    if valid_games == 0: 
        return None
    
    final_score = (weighted_sum / valid_games) * 100
    
    return {
        'weighted_score': final_score,
        'n_games': len(opponents_faced),
        'n_ranked': sum(1 for o in opponents_faced if o['raw']['rank'] is not None),
        'opponents': opponents_faced
    }

def print_sos_report(G, team_name, start_year, end_year, non_conf_only):
    """
    Prints a detailed Schedule Strength report for a single team,
    including their league-wide rank based on Weighted SOS.
    """
    real_team = utils.resolve_team_name(G, team_name)
    if not real_team: 
        return
    
    stats_db = data.load_season_stats()
    if not stats_db:
        print("[ERROR] No stats DB found. Run build_stats_db.py first.")
        return

    # 1. Calculate Own SOS
    my_sos = calculate_sos(G, real_team, start_year, end_year, non_conf_only, stats_db)
    if not my_sos:
        print(f"   No games found for {real_team} matching criteria.")
        return

    # 2. Calculate League-Wide Rank
    # Compares against every other team currently in the graph (controlled by --div)
    print("   Calculating rank among selected peers...", end='\r')
    
    all_sos = []
    for node in G.nodes():
        s = calculate_sos(G, node, start_year, end_year, non_conf_only, stats_db)
        # Only rank teams with enough data (min 3 games)
        if s and s['n_games'] >= 3:
            all_sos.append({'team': node, 'score': s['weighted_score']})
    
    # Sort descending (Hardest weighted schedule first)
    all_sos.sort(key=lambda x: x['score'], reverse=True)
    
    my_rank = next((i+1 for i, x in enumerate(all_sos) if x['team'] == real_team), None)
    total_ranked = len(all_sos)

    # 3. Print Header
    label = "OUT-OF-CONFERENCE" if non_conf_only else "OVERALL"
    print(f"\n[SOS] SCHEDULE STRENGTH: {real_team.upper()} ({start_year}-{end_year})")
    print(f"      Filter: {label}")
    print("="*85)
    
    score = my_sos['weighted_score']
    print(f"      Weighted Score:   {score:.1f}  (FBS=1.0, FCS=0.6, D2=0.4)")
    
    if my_rank:
        percentile = (my_rank / total_ranked) * 100
        print(f"      Schedule Rank:    #{my_rank} of {total_ranked} (Top {percentile:.1f}%)")
    else:
        print(f"      Schedule Rank:    N/A (Not enough games)")
        
    # 4. Gather Opponent Details
    opponents = my_sos['opponents']
    
    # Add Result Strings (W/L)
    # We need to look up game data again or assume passed. 
    # For speed, let's just grab it from graph since we are already iterating.
    for o in opponents:
        nbr = o['name']
        year = o['year']
        
        # Find the specific game in history to get the score
        history = G.get_edge_data(real_team, nbr)['history']
        target_game = next((g for g in history if g['season'] == year), None)
        
        res = "N/A"
        if target_game and target_game.get('home_score') is not None:
            if target_game['home'] == real_team:
                us, them = target_game['home_score'], target_game['away_score']
            else:
                us, them = target_game['away_score'], target_game['home_score']
            
            if us > them: res = f"W {us}-{them}"
            elif them > us: res = f"L {us}-{them}"
            else: res = f"T {us}-{them}"
        o['result'] = res

    # Sort by Weighted Contribution (Raw Pct * Weight)
    opponents.sort(key=lambda x: ((x['raw']['pct'] * x['weight']), x['raw']['rank'] if x['raw']['rank'] else 999), reverse=True)
    
    print(f"\n[TOP] TOUGHEST OPPONENTS (Weighted)")
    print(f"{'Year':<6} | {'Opponent':<20} | {'Div':<5} | {'Rec':<8} | {'Raw %':<6} | {'Wgt Score'}")
    print("-" * 85)
    
    for o in opponents[:20]:
        r = o['raw']
        rec_str = f"{r['w']}-{r['l']}"
        raw_pct = r['pct'] * 100
        wgt_score = raw_pct * o['weight']
        
        # Add Rank indicator to name if ranked
        name_display = o['name']
        if r['rank']:
            name_display += f" (#{r['rank']})"
            
        print(f"{o['year']:<6} | {name_display:<20} | {o['div'].upper():<5} | {rec_str:<8} | {raw_pct:<6.1f} | {wgt_score:.1f}")

def print_sos_leaderboard(G, start_year, end_year, non_conf_only):
    """
    Calculates Weighted SOS for every team in the graph and prints a leaderboard.
    """
    stats_db = data.load_season_stats()
    if not stats_db:
        print("[ERROR] No stats DB found. Run build_stats_db.py first.")
        return

    label = "OUT-OF-CONFERENCE" if non_conf_only else "OVERALL"
    print(f"\n[LEADERBOARD] SCHEDULE STRENGTH ({start_year}-{end_year})")
    print(f"              Filter: {label} (Weighted by Division)")
    print("="*75)
    
    results = []
    nodes = list(G.nodes())
    total = len(nodes)
    
    print(f"   Analyzing {total} teams...", end='\r')
    
    for i, team in enumerate(nodes):
        if i % 50 == 0: 
            print(f"   Analyzing {i}/{total} teams...", end='\r')
        
        sos = calculate_sos(G, team, start_year, end_year, non_conf_only, stats_db)
        
        # Filter out teams with too few games
        if sos and sos['n_games'] >= 3:
            results.append({
                'team': team,
                'score': sos['weighted_score'],
                'games': sos['n_games'],
                'ranked': sos['n_ranked']
            })
            
    # Sort by Weighted Score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n{'Rank':<4} | {'Team':<25} | {'Wgt Score':<10} | {'Gms':<5} | {'Ranked Opps'}")
    print("-" * 75)
    
    # Print Top 50
    for i, r in enumerate(results[:50]):
        print(f"{i+1:<4} | {r['team']:<25} | {r['score']:.1f}       | {r['games']:<5} | {r['ranked']}")


# ==========================================
# 2. STANDARD STATS FUNCTIONS
# ==========================================

def print_conference_stats(G, conf_1_teams, conf_1_name, conf_2_teams=None, conf_2_name=None, aggregate=False):
    # --- MODE A: CONFERENCE VS CONFERENCE ---
    if conf_2_teams:
        print(f"\n[VS] CONFERENCE SHOWDOWN: {conf_1_name} vs {conf_2_name}")
        print("="*65)
        
        matchups = []
        t_wins = [0, 0] # [Conf1 Wins, Conf2 Wins]
        total = 0
        
        for t1 in conf_1_teams:
            if not G.has_node(t1): continue
            
            for t2 in conf_2_teams:
                if not G.has_node(t2): continue
                
                if G.has_edge(t1, t2):
                    history = G.get_edge_data(t1, t2)['history']
                    wins = 0
                    pts_diff = 0
                    
                    for g in history:
                        if g.get('home_score') is None: continue
                        
                        s1, s2 = 0, 0
                        if g['home'] == t1:
                            s1, s2 = g['home_score'], g['away_score']
                        else:
                            s1, s2 = g['away_score'], g['home_score']
                            
                        if s1 > s2: wins += 1
                        pts_diff += (s1 - s2)
                        
                    count = len(history)
                    t_wins[0] += wins
                    t_wins[1] += (count - wins)
                    total += count
                    
                    if not aggregate:
                        matchups.append({
                            'm': f"{t1} vs {t2}", 
                            'r': f"{wins}-{count-wins}", 
                            'l': history[-1]['season'], 
                            'd': pts_diff
                        })
        
        if total == 0:
            print("   No games found.")
            return

        pct = (t_wins[0]/total)*100
        print(f"   Record: {t_wins[0]}-{t_wins[1]} ({pct:.1f}%)")
        
        if not aggregate:
            print(f"\n[SERIES] BREAKDOWN")
            print(f"{'Matchup':<35} | {'Record':<10} | {'Diff':<6} | {'Last'}")
            print("-" * 65)
            matchups.sort(key=lambda x: x['l'], reverse=True)
            for m in matchups[:25]:
                print(f"{m['m']:<35} | {m['r']:<10} | {m['d']:<+6} | {m['l']}")

    # --- MODE B: SINGLE CONFERENCE REPORT ---
    else:
        print(f"\n[REPORT] CONFERENCE REPORT: {conf_1_name}")
        print("="*65)
        
        leaderboard = []
        agg_wins = 0
        agg_games = 0
        
        for t in conf_1_teams:
            if not G.has_node(t): continue
            
            w, l, t_cnt = 0, 0, 0
            pf, pa = 0, 0
            
            for nbr in G.neighbors(t):
                history = G.get_edge_data(t, nbr)['history']
                for g in history:
                    if g.get('home_score') is None: continue
                    
                    if g['home'] == t: 
                        s1, s2 = g['home_score'], g['away_score']
                    else: 
                        s1, s2 = g['away_score'], g['home_score']
                        
                    pf += s1
                    pa += s2
                    
                    if s1 > s2: w += 1
                    elif s2 > s1: l += 1
                    else: t_cnt += 1
            
            tot = w + l + t_cnt
            if tot > 0:
                win_pct = w / tot
                leaderboard.append({
                    't': t, 'pct': win_pct, 
                    'rec': f"{w}-{l}-{t_cnt}", 
                    'd': pf - pa,
                    'wins': w
                })
                agg_wins += w
                agg_games += tot

        leaderboard.sort(key=lambda x: x['pct'], reverse=True)
        
        if aggregate:
            print(f"\n[AGGREGATE] STATS (All Members Combined)")
            print(f"   Total Games:  {agg_games}")
            if agg_games > 0:
                print(f"   Win %:        {(agg_wins/agg_games)*100:.1f}%")
                print(f"   Record:       {agg_wins}-{agg_games-agg_wins}")
            
            if leaderboard:
                best = leaderboard[0]
                worst = leaderboard[-1]
                print(f"\n   Top Performer:    {best['t']} ({best['rec']})")
                print(f"   Lowest Performer: {worst['t']} ({worst['rec']})")
        else:
            print(f"{'Team':<25} | {'Record':<10} | {'Win %':<6} | {'Diff':<6}")
            print("-" * 65)
            for r in leaderboard:
                print(f"{r['t']:<25} | {r['rec']:<10} | {r['pct']*100:.1f}%  | {r['d']:+}")

def print_team_stats(G, centroid, non_conf_only=False):
    real = utils.resolve_team_name(G, centroid)
    if not real: return
    
    label = "OUT-OF-CONFERENCE" if non_conf_only else "HISTORICAL"
    print(f"\n[STATS] {label}: {real.upper()}")
    
    stats = []
    
    for nbr in G.neighbors(real):
        hist = G.get_edge_data(real, nbr)['history']
        valid = []
        d = 0
        
        for g in hist:
            if non_conf_only:
                if g.get('home_conf') and g.get('away_conf'):
                    if data.normalize_conf_name(g['home_conf']) == data.normalize_conf_name(g['away_conf']):
                        continue
            
            if g.get('home_score') is not None:
                valid.append(g)
                if g['home'] == real:
                    d += (g['home_score'] - g['away_score'])
                else:
                    d += (g['away_score'] - g['home_score'])
            
        if valid:
            stats.append({
                'op': nbr, 
                'c': len(valid), 
                'd': d, 
                'l': hist[-1]['season']
            })
    
    stats.sort(key=lambda x: x['c'], reverse=True)
    
    print(f"\n[TOP] MOST PLAYED OPPONENTS")
    for s in stats[:10]:
        print(f"   vs {s['op']:<25}: {s['c']:<3} games ({s['d']:+4} diff) | Last: {s['l']}")

    significant = [s for s in stats if s['c'] >= 3]
    if significant:
        for s in significant:
            s['avg'] = s['d'] / s['c']
        significant.sort(key=lambda x: x['avg']) 
        print(f"\n[TOUGHEST] (Min 3 Games)")
        for s in significant[:3]:
            print(f"   vs {s['op']:<25}: {s['avg']:+.1f} ppg")

def analyze_connection(G, centroid, target):
    real_centroid = utils.resolve_team_name(G, centroid)
    real_target = utils.resolve_team_name(G, target)
    if not real_centroid or not real_target: return
    
    if G.has_edge(real_centroid, real_target):
        hist = G.get_edge_data(real_centroid, real_target)['history']
        w, l, t = 0, 0, 0
        for g in hist:
            if g.get('home_score') is None: continue
            s1, s2 = (g['home_score'], g['away_score']) if g['home'] == real_centroid else (g['away_score'], g['home_score'])
            if s1 > s2: w += 1
            elif s2 > s1: l += 1
            else: t += 1
        
        last = hist[-1]
        res = f"{last['home']} {last['home_score']}-{last['away_score']} {last['away']}"
        print(f"\n[MATCH] {real_centroid} vs {real_target}")
        print(f"   Record: {w}-{l}-{t}")
        print(f"   Last:   {last['season']} ({res})")
    else:
        try:
            path = nx.shortest_path(G, source=real_centroid, target=real_target)
            print(f"\n[CHAIN] Connection ({len(path)-1} Degrees):")
            for i in range(len(path)-1):
                t1, t2 = path[i], path[i+1]
                last_met = G.get_edge_data(t1, t2)['last_met']
                print(f"   {i+1}. {t1} played {t2} ({last_met})")
        except:
            print("   No connection found.")

def list_unplayed(G, centroid, universe):
    real = utils.resolve_team_name(G, centroid)
    if not real: return
    played = set(G.neighbors(real))
    valid = {t for t in universe if G.has_node(t)}
    never = sorted(list(valid - played - {real}))
    print(f"\n[UNPLAYED] {real} has never played {len(never)} teams:")
    if never:
        col = max(len(t) for t in never) + 2
        for i in range(0, len(never), 3):
             print("".join(w.ljust(col) for w in never[i:i+3]))

def print_league_diameter(G):
    if not nx.is_connected(G): 
        G = G.subgraph(max(nx.connected_components(G), key=len))
    print(f"\n[DIAMETER] {nx.diameter(G)} Degrees")

def print_overall_stats(G):
    print("\n[LEAGUE] Stats...")
    matchups = sorted([{'m': f"{u} vs {v}", 'c': len(d['history'])} for u,v,d in G.edges(data=True)], key=lambda x: x['c'], reverse=True)
    print("\n[RIVALRIES] Most Played")
    for m in matchups[:5]: 
        print(f"   {m['m']:<40} | {m['c']}")

# ==========================================
# 3. MAIN EXECUTION BLOCK
# ==========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('centroid', type=str, nargs='?')
    parser.add_argument('target', type=str, nargs='?')
    parser.add_argument('--div', nargs='+', default=['fbs'])
    parser.add_argument('--conf', nargs='+')
    parser.add_argument('--aggregate', action='store_true')
    parser.add_argument('--start', type=int)
    parser.add_argument('--end', type=int)
    parser.add_argument('--non-conf', action='store_true')

    args = parser.parse_args()
    start_year = args.start if args.start else 1869
    end_year = args.end if args.end else datetime.now().year

    # 1. LOAD DATA
    games = data.load_games_data()
    
    # Apply Time Filter immediately
    if args.start or args.end:
        print(f"[INFO] Timeframe: {start_year}-{end_year}")
        initial_len = len(games)
        games = [g for g in games if start_year <= g['season'] <= end_year]
        print(f"       Games reduced from {initial_len} to {len(games)}")

    # 2. BUILD GRAPH
    div_filter = data.get_team_filter(args.div)
    G = graph.build_graph(games, fbs_filter_set=div_filter)
    print(f"[INFO] Nodes: {G.number_of_nodes()}")

    # 3. ROUTE COMMANDS
    if args.conf:
        c1 = args.conf[0]
        c1_teams = data.get_teams_in_conference_range(c1, start_year, end_year)
        
        c2 = args.conf[1] if len(args.conf) > 1 else None
        c2_teams = data.get_teams_in_conference_range(c2, start_year, end_year) if c2 else None
        
        print_conference_stats(G, c1_teams, c1, c2_teams, c2, args.aggregate)

    elif args.centroid:
        cmd = args.centroid.lower()
        
        # A. Global Commands
        if cmd == "overall":
            if args.target == "sos": 
                print_sos_leaderboard(G, start_year, end_year, args.non_conf)
            elif args.target == "diameter": 
                print_league_diameter(G)
            else: 
                print_overall_stats(G)
        
        # B. Team Specific Commands
        elif args.target and args.target.lower() == "sos":
            print_sos_report(G, args.centroid, start_year, end_year, args.non_conf)
            
        elif args.target and args.target.lower() == "stats":
            print_team_stats(G, args.centroid, non_conf_only=args.non_conf)
            
        elif args.target:
            analyze_connection(G, args.centroid, args.target)
            
        else:
            univ = div_filter if div_filter else set(G.nodes())
            list_unplayed(G, args.centroid, univ)
            
    else:
        print("Usage Examples:")
        print("  python3 main.py Oregon stats --non-conf")
        print("  python3 main.py Oregon sos --start 2014 --end 2024 --div fbs")
        print("  python3 main.py overall sos --start 2023 --end 2023")