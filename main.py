# Suppress Warnings
import warnings
import sys
warnings.filterwarnings("ignore", module="urllib3")
import urllib3
urllib3.disable_warnings()

import argparse
import networkx as nx
import data
import graph
import utils

def print_team_stats(G, centroid):
    real_centroid = utils.resolve_team_name(G, centroid)
    if not real_centroid:
        print(f"[ERROR] Team '{centroid}' not found.")
        return

    print(f"\nHISTORICAL STATS FOR: {real_centroid.upper()}")
    print("="*60)

    stats = []
    for opponent in G.neighbors(real_centroid):
        edge_data = G.get_edge_data(real_centroid, opponent)
        games = edge_data['history']
        
        count = len(games)
        total_diff = 0
        
        for g in games:
            if g.get('home_score') is None or g.get('away_score') is None:
                continue
            if g['home'] == real_centroid:
                diff = g['home_score'] - g['away_score']
            else:
                diff = g['away_score'] - g['home_score']
            total_diff += diff
            
        stats.append({
            'opponent': opponent,
            'count': count,
            'total_diff': total_diff,
            'avg_diff': total_diff / count,
            'last_met': edge_data['last_met']
        })

    stats.sort(key=lambda x: x['count'], reverse=True)
    
    print(f"\nMOST PLAYED OPPONENTS")
    print(f"{'Opponent':<20} | {'Games':<5} | {'Tot Diff':<8} | {'Last Met'}")
    print("-" * 50)
    for s in stats[:5]:
        sign = "+" if s['total_diff'] > 0 else ""
        print(f"{s['opponent']:<20} | {s['count']:<5} | {sign}{s['total_diff']:<8} | {s['last_met']}")

    significant = [s for s in stats if s['count'] >= 3]
    if significant:
        significant.sort(key=lambda x: x['avg_diff'], reverse=True)
        print(f"\nDOMINANT MATCHUPS (Best Avg Point Diff, Min 3 Games)")
        for s in significant[:3]:
            print(f"   vs {s['opponent']:<15}: +{s['avg_diff']:.1f} ppg ({s['count']} gms)")

        significant.sort(key=lambda x: x['avg_diff'])
        print(f"\nTOUGHEST OPPONENTS (Worst Avg Point Diff, Min 3 Games)")
        for s in significant[:3]:
            print(f"   vs {s['opponent']:<15}: {s['avg_diff']:.1f} ppg ({s['count']} gms)")

def print_overall_stats(G):
    """Scans the ENTIRE graph to find league-wide records."""
    print("\nCALCULATING LEAGUE-WIDE HISTORICAL STATS...")
    print("(This scans every rivalry in FBS history)\n")
    
    matchups = []
    
    # Iterate over all edges (u, v, data)
    for u, v, data in G.edges(data=True):
        games = data['history']
        count = len(games)
        if count == 0: continue
        
        # Calculate stats for this specific pair
        u_wins = 0
        v_wins = 0
        ties = 0
        
        # We track point diff relative to Team U
        total_diff_u = 0 
        
        for g in games:
            if g.get('home_score') is None or g.get('away_score') is None:
                continue
                
            s_home = g['home_score']
            s_away = g['away_score']
            
            # Figure out who is U and who is V in this specific game record
            # (The edge is undirected, but the game record has specific home/away)
            if g['home'] == u:
                diff = s_home - s_away
            else:
                diff = s_away - s_home
            
            total_diff_u += diff
            
            # Win/Loss
            if diff > 0: u_wins += 1
            elif diff < 0: v_wins += 1
            else: ties += 1
            
        # Calculate Dominance Metric (Win %)
        # We only care about the winner's percentage to see how "lopsided" it is
        total_decisive = u_wins + v_wins
        if total_decisive > 0:
            win_pct = max(u_wins, v_wins) / total_decisive
            leader = u if u_wins > v_wins else v
        else:
            win_pct = 0.0
            leader = "Tied"

        matchups.append({
            'matchup': f"{u} vs {v}",
            'count': count,
            'total_diff_abs': abs(total_diff_u), # Magnitude of scoring gap
            'avg_diff_abs': abs(total_diff_u) / count,
            'leader': leader,
            'win_pct': win_pct,
            'record': f"{u_wins}-{v_wins}-{ties}"
        })

    # --- REPORT 1: MOST PLAYED RIVALRIES ---
    matchups.sort(key=lambda x: x['count'], reverse=True)
    print(f"MOST PLAYED RIVALRIES (All Time)")
    print(f"{'Matchup':<40} | {'Games':<5} | {'Leader'}")
    print("-" * 65)
    for m in matchups[:10]:
        print(f"{m['matchup']:<40} | {m['count']:<5} | {m['leader']}")

    # --- REPORT 2: MOST UNEVEN SERIES (Min 20 Games) ---
    # We look for highest Win %
    veteran_series = [m for m in matchups if m['count'] >= 20]
    veteran_series.sort(key=lambda x: x['win_pct'], reverse=True)
    
    print(f"\nMOST ONE-SIDED SERIES (Min 20 Games)")
    print(f"{'Matchup':<40} | {'Win %':<6} | {'Leader'}")
    print("-" * 65)
    for m in veteran_series[:10]:
        print(f"{m['matchup']:<40} | {m['win_pct']:.1%} | {m['leader']}")

    # --- REPORT 3: BIGGEST POINT GAPS (Cumulative) ---
    # Who has outscored their rival the most over history?
    matchups.sort(key=lambda x: x['total_diff_abs'], reverse=True)
    
    print(f"\nLARGEST CUMULATIVE POINT DIFFERENTIALS")
    print(f"(Total margin of victory across all games played)")
    print(f"{'Matchup':<40} | {'Diff':<6} | {'Leader'}")
    print("-" * 65)
    for m in matchups[:10]:
        print(f"{m['matchup']:<40} | +{m['total_diff_abs']:<5} | {m['leader']}")

def analyze_connection(G, centroid, target):
    real_centroid = utils.resolve_team_name(G, centroid)
    real_target = utils.resolve_team_name(G, target)
    
    if not real_centroid or not real_target:
        print("[ERROR] Teams not found.")
        return

    if G.has_edge(real_centroid, real_target):
        history = G.get_edge_data(real_centroid, real_target)['history']
        
        # --- 1. Initialize Counters ---
        stats = {
            'overall': {'w': 0, 'l': 0, 't': 0, 'pts_c': 0, 'pts_t': 0},
            'at_centroid': {'w': 0, 'l': 0, 't': 0}, # Games played at Centroid's home
            'at_target': {'w': 0, 'l': 0, 't': 0}     # Games played at Target's home
        }
        
        valid_games = 0

        # --- 2. Iterate History ---
        for g in history:
            if g.get('home_score') is None or g.get('away_score') is None:
                continue
                
            valid_games += 1
            
            # Determine scores and winner relative to Centroid
            if g['home'] == real_centroid:
                sc = g['home_score']
                st = g['away_score']
                location = 'at_centroid'
            else:
                sc = g['away_score']
                st = g['home_score']
                location = 'at_target' # Note: Neutral sites will fall into one of these based on 'home' designation
            
            stats['overall']['pts_c'] += sc
            stats['overall']['pts_t'] += st
            
            # Update Records
            if sc > st:
                stats['overall']['w'] += 1
                stats[location]['w'] += 1
            elif sc < st:
                stats['overall']['l'] += 1
                stats[location]['l'] += 1
            else:
                stats['overall']['t'] += 1
                stats[location]['t'] += 1

        # --- 3. Calculate Derived Stats ---
        def calc_pct(record):
            total = record['w'] + record['l'] + record['t']
            if total == 0: return 0.0
            return (record['w'] / total) * 100

        ov_pct = calc_pct(stats['overall'])
        home_pct = calc_pct(stats['at_centroid'])
        away_pct = calc_pct(stats['at_target'])
        
        tot_diff = stats['overall']['pts_c'] - stats['overall']['pts_t']
        avg_c = stats['overall']['pts_c'] / valid_games if valid_games else 0
        avg_t = stats['overall']['pts_t'] / valid_games if valid_games else 0

        # --- 4. Format "Last Met" String ---
        last_game = history[-1]
        if last_game.get('home_score') is not None:
            # Re-determine scores for the specific last game logic
            h_team = last_game['home']
            a_team = last_game['away']
            h_score = last_game['home_score']
            a_score = last_game['away_score']
            
            if h_score > a_score:
                winner = h_team
                w_score, l_score = h_score, a_score
            elif a_score > h_score:
                winner = a_team
                w_score, l_score = a_score, h_score
            else:
                winner = "Tie"
                w_score, l_score = h_score, a_score
            
            if winner == "Tie":
                last_met_str = f"{last_game['season']} (Tie {w_score}-{l_score})"
            else:
                last_met_str = f"{last_game['season']} ({winner} won {w_score}-{l_score})"
        else:
            last_met_str = f"{last_game['season']} (N/A)"

        # --- 5. Print Report ---
        print(f"\nMATCHUP FOUND: {real_centroid} vs {real_target}")
        print("-" * 60)
        
        # Overall Record
        rec = stats['overall']
        print(f"   Record:           {rec['w']}-{rec['l']}-{rec['t']} ({ov_pct:.1f}%)")
        
        # Home Split
        h_rec = stats['at_centroid']
        print(f"   At {real_centroid}:".ljust(21) + f"{h_rec['w']}-{h_rec['l']}-{h_rec['t']} ({home_pct:.1f}%)")
        
        # Away Split
        a_rec = stats['at_target']
        print(f"   At {real_target}:".ljust(21) + f"{a_rec['w']}-{a_rec['l']}-{a_rec['t']} ({away_pct:.1f}%)")
        
        print("-" * 60)
        print(f"   Total Diff:       {tot_diff:+} (favors {real_centroid if tot_diff > 0 else real_target})")
        print(f"   Avg Score:        {real_centroid} {avg_c:.1f} - {avg_t:.1f} {real_target}")
        print(f"   Last Met:         {last_met_str}")
        print("-" * 60)

    else:
        try:
            path = nx.shortest_path(G, source=real_centroid, target=real_target)
            print(f"\n🔗 Connection Chain ({len(path)-1} Degrees of Separation):")
            for i in range(len(path) - 1):
                t1, t2 = path[i], path[i+1]
                year = G.get_edge_data(t1, t2)['last_met']
                print(f"   {i+1}. {t1} played {t2} ({year})")
        except:
            print("   No connection found.")

def list_unplayed(G, centroid, universe):
    real_centroid = utils.resolve_team_name(G, centroid)
    if not real_centroid:
        print(f"[ERROR] Team '{centroid}' not found.")
        return

    played = set(G.neighbors(real_centroid))
    never = sorted(list(universe - played - {real_centroid}))
    
    print(f"\n {real_centroid} has never played the following {len(never)} FBS teams:")
    
    if never:
        col_width = max(len(t) for t in never) + 2
        for i in range(0, len(never), 3):
            print("".join(word.ljust(col_width) for word in never[i:i+3]))

def print_conference_stats(G, conf_1_teams, conf_1_name, conf_2_teams=None, conf_2_name=None, aggregate=False):
    # --- MODE A: CONFERENCE VS CONFERENCE (Unchanged) ---
    if conf_2_teams:
        print(f"\nCONFERENCE SHOWDOWN: {conf_1_name} vs {conf_2_name}")
        print("="*60)
        
        matchups = []
        total_c1_wins = 0
        total_c2_wins = 0
        total_games = 0
        total_diff = 0

        for t1 in conf_1_teams:
            if not G.has_node(t1): continue
            for t2 in conf_2_teams:
                if not G.has_node(t2): continue
                if G.has_edge(t1, t2):
                    history = G.get_edge_data(t1, t2)['history']
                    wins_t1 = 0
                    pts_t1, pts_t2 = 0, 0
                    
                    for g in history:
                        if g.get('home_score') is None: continue
                        if g['home'] == t1:
                            s1, s2 = g['home_score'], g['away_score']
                        else:
                            s1, s2 = g['away_score'], g['home_score']
                        
                        if s1 > s2: wins_t1 += 1
                        pts_t1 += s1
                        pts_t2 += s2
                    
                    g_count = len(history)
                    diff = pts_t1 - pts_t2
                    
                    total_games += g_count
                    total_c1_wins += wins_t1
                    total_c2_wins += (g_count - wins_t1)
                    total_diff += diff
                    
                    if not aggregate:
                        matchups.append({
                            'matchup': f"{t1} vs {t2}",
                            'record': f"{wins_t1}-{g_count - wins_t1}",
                            'last': history[-1]['season'],
                            'diff': diff
                        })

        if total_games == 0:
            print("   No historical games found between these conferences in the selected timeframe.")
            return

        win_pct = (total_c1_wins / total_games) * 100 if total_games > 0 else 0
        print(f"AGGREGATE RECORD")
        print(f"   Total Games:  {total_games}")
        print(f"   {conf_1_name} Wins:  {total_c1_wins} ({win_pct:.1f}%)")
        print(f"   {conf_2_name} Wins:  {total_c2_wins} ({100-win_pct:.1f}%)")
        print(f"   Point Diff:   {total_diff:+} (favors {conf_1_name if total_diff > 0 else conf_2_name})")
        
        if not aggregate:
            print(f"\n📜 SERIES BREAKDOWN (Active Rivalries)")
            print(f"{'Matchup':<35} | {'Record':<10} | {'Diff':<6} | {'Last'}")
            print("-" * 65)
            matchups.sort(key=lambda x: x['last'], reverse=True)
            for m in matchups[:25]:
                print(f"{m['matchup']:<35} | {m['record']:<10} | {m['diff']:<+6} | {m['last']}")
    
    # --- MODE B: SINGLE CONFERENCE REPORT ---
    else:
        print(f"\nCONFERENCE REPORT: {conf_1_name}")
        # Disclaimer: Groups are based on CURRENT 2025 membership
        print(f"(Performance of current {conf_1_name} members during selected timeframe)")
        print("="*60)
        
        # 1. Gather Stats for Every Member Team
        leaderboard = []
        total_conf_wins = 0
        total_conf_games = 0
        
        for t in conf_1_teams:
            if not G.has_node(t): continue
            
            wins, losses, ties = 0, 0, 0
            pf, pa = 0, 0
            
            # Look at every game this team played in the graph (which is already time-filtered)
            for nbr in G.neighbors(t):
                history = G.get_edge_data(t, nbr)['history']
                for g in history:
                    if g.get('home_score') is None: continue
                    
                    s_us, s_them = 0, 0
                    if g['home'] == t:
                        s_us, s_them = g['home_score'], g['away_score']
                    else:
                        s_us, s_them = g['away_score'], g['home_score']
                    
                    pf += s_us
                    pa += s_them
                    
                    if s_us > s_them: wins += 1
                    elif s_them > s_us: losses += 1
                    else: ties += 1
            
            total_games = wins + losses + ties
            if total_games == 0: continue
            
            win_pct = (wins / total_games) * 100
            
            leaderboard.append({
                'team': t,
                'w': wins, 'l': losses, 't': ties,
                'pct': win_pct,
                'diff': pf - pa
            })
            
            total_conf_wins += wins
            total_conf_games += total_games

        # 2. Sort by Winning Percentage
        leaderboard.sort(key=lambda x: x['pct'], reverse=True)
        
        # 3. Print the Table (or Aggregate Summary)
        if aggregate:
            # Improved Aggregate View
            print(f"AGGREGATE STATS (All Members)")
            print(f"   Combined Record: {total_conf_wins}-{total_conf_games - total_conf_wins}")
            if total_conf_games > 0:
                print(f"   Combined Win %:  {(total_conf_wins/total_conf_games)*100:.1f}%")
            
            print(f"\nTOP PERFORMER")
            if leaderboard:
                best = leaderboard[0]
                print(f"   {best['team']}: {best['w']}-{best['l']}-{best['t']} ({best['pct']:.1f}%)")
                
            print(f"\nLOWEST PERFORMER")
            if leaderboard:
                worst = leaderboard[-1]
                print(f"   {worst['team']}: {worst['w']}-{worst['l']}-{worst['t']} ({worst['pct']:.1f}%)")

        else:
            # FULL LEADERBOARD VIEW
            print(f"{'Team':<25} | {'Record':<10} | {'Win %':<6} | {'Diff':<6}")
            print("-" * 65)
            for s in leaderboard:
                rec_str = f"{s['w']}-{s['l']}-{s['t']}"
                print(f"{s['team']:<25} | {rec_str:<10} | {s['pct']:.1f}%  | {s['diff']:+}")

def print_league_diameter(G):
    print("\nCALCULATING LEAGUE DIAMETER...")
    print("(Finding the two teams furthest apart in history...)")
    
    # 1. Get Largest Connected Component
    # (Safety: If the graph is disconnected, diameter is infinite, so we focus on the main cluster)
    if not nx.is_connected(G):
        print("[WARN] Graph is not fully connected. Analyzing the largest cluster only.")
        G = G.subgraph(max(nx.connected_components(G), key=len)).copy()

    # 2. Calculate Diameter
    try:
        # This might take 5-10 seconds for large graphs
        diameter = nx.diameter(G)
        periphery = nx.periphery(G) # Nodes that are 'diameter' away from someone
    except Exception as e:
        print(f"[ERROR] Could not calculate diameter: {e}")
        return

    print(f"\nLEAGUE DIAMETER: {diameter} DEGREES")
    print(f"There are {len(periphery)} teams on the edge of the college football universe.")
    
    # 3. Find a specific pair to show the path
    # (Not all periphery nodes are far from EACH OTHER, only from 'someone'. 
    # We must find a pair that is exactly 'diameter' apart.)
    
    found_pair = False
    import itertools
    
    # Check pairs within the periphery to find the max distance example
    # (Limit checks to avoid hanging if periphery is huge)
    for u, v in itertools.combinations(periphery, 2):
        try:
            dist = nx.shortest_path_length(G, u, v)
            if dist == diameter:
                print(f"\n🪐 EXTREME MATCHUP FOUND: {u} vs {v}")
                
                path = nx.shortest_path(G, source=u, target=v)
                print(f"   The Longest Road ({len(path)-1} Degrees):")
                for i in range(len(path) - 1):
                    t1, t2 = path[i], path[i+1]
                    year = G.get_edge_data(t1, t2)['last_met']
                    print(f"     {i+1}. {t1} played {t2} ({year})")
                
                found_pair = True
                break # Just show one example to keep output clean
        except:
            continue
            
    if not found_pair:
        print("   (Could not isolate a single specific pair in the periphery subset quickly.)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('centroid', type=str, nargs='?')
    parser.add_argument('target', type=str, nargs='?')
    parser.add_argument('--div', nargs='+', default=['fbs'], choices=['fbs', 'fcs', 'ii', 'iii', 'all'])
    parser.add_argument('--conf', nargs='+', help="Conference filter")
    parser.add_argument('--aggregate', action='store_true')
    parser.add_argument('--start', type=int, help="Start Year")
    parser.add_argument('--end', type=int, help="End Year")

    args = parser.parse_args()
    
    # 1. Defaults
    start_year = args.start if args.start else 1869
    end_year = args.end if args.end else datetime.now().year
    
    # 2. Load Data & Filter Games by Year
    games = data.load_games_data()
    
    if args.start or args.end:
        print(f"[INFO] Timeframe Filter: {start_year}-{end_year}")
        games = [g for g in games if start_year <= g['season'] <= end_year]

    # 3. Build Graph
    division_filter = data.get_team_filter(args.div) # Make sure this function exists in data.py
    G = graph.build_graph(games, fbs_filter_set=division_filter)
    
    # 4. Logic Router
    if args.conf:
        c1_input = args.conf[0]
        
        c1_teams = data.get_teams_in_conference_range(c1_input, start_year, end_year)
        
        c2_teams = None
        c2_input = None
        if len(args.conf) > 1:
            c2_input = args.conf[1]
            c2_teams = data.get_teams_in_conference_range(c2_input, start_year, end_year)
            
        # Pass the resolved names (or original inputs) to the printer
        # Note: resolve_conference_name returns the official name, so we could update c1_input
        # but passing the input string is fine for display.
        
        print_conference_stats(G, c1_teams, c1_input, c2_teams, c2_input, args.aggregate)

    elif args.centroid:
        if args.centroid.lower() == "overall":
            if args.target == "diameter":
                print_league_diameter(G)
            else:
                print_overall_stats(G)
        elif args.target and args.target.lower() == "stats":
            print_team_stats(G, args.centroid)
        elif args.target:
            analyze_connection(G, args.centroid, args.target)
        else:
            universe = division_filter if division_filter else set(G.nodes())
            list_unplayed(G, args.centroid, universe)