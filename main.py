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

# --- SOS LOGIC (Schedule Strength) ---

def calculate_sos(G, team, start_year, end_year, non_conf_only, stats_db):
    """Calculates Aggregate Opponent Win % for a team."""
    if not G.has_node(team): return None

    opponents_faced = []
    
    for nbr in G.neighbors(team):
        history = G.get_edge_data(team, nbr)['history']
        for g in history:
            year = g['season']
            if year < start_year or year > end_year: continue
            
            if non_conf_only:
                h_conf = g.get('home_conf')
                a_conf = g.get('away_conf')
                if h_conf and a_conf:
                    # Treat Indep vs Indep as Conf game
                    if data.normalize_conf_name(h_conf) == data.normalize_conf_name(a_conf):
                        continue

            opp_stats = data.get_team_stats(nbr, year, stats_db)
            opponents_faced.append(opp_stats)

    if not opponents_faced: return None

    total_wins = sum(o['w'] for o in opponents_faced)
    total_games = sum(o['w'] + o['l'] + o['t'] for o in opponents_faced)
    
    if total_games == 0: return None
    
    return {
        'opp_win_pct': (total_wins / total_games) * 100,
        'n_games': len(opponents_faced),
        'n_ranked': sum(1 for o in opponents_faced if o['rank'] is not None),
        'raw_opponents': opponents_faced
    }

def print_sos_report(G, team_name, start_year, end_year, non_conf_only):
    real_team = utils.resolve_team_name(G, team_name)
    if not real_team: return
    
    stats_db = data.load_season_stats()
    if not stats_db:
        print("[ERROR] No stats DB found. Run build_stats_db.py first.")
        return

    # 1. Calculate Own SOS
    my_sos = calculate_sos(G, real_team, start_year, end_year, non_conf_only, stats_db)
    if not my_sos:
        print("   No games found matching criteria.")
        return

    # 2. Calculate League-Wide Rank
    # We compare against all other teams in the current graph (filtered by division/time)
    print("   Calculating league-wide rank...", end='\r')
    all_sos = []
    for node in G.nodes():
        s = calculate_sos(G, node, start_year, end_year, non_conf_only, stats_db)
        if s and s['n_games'] >= 3: # Minimum 3 games to be ranked
            all_sos.append({'team': node, 'pct': s['opp_win_pct']})
    
    # Sort descending (Hardest first)
    all_sos.sort(key=lambda x: x['pct'], reverse=True)
    
    # Find my rank
    my_rank = next((i+1 for i, x in enumerate(all_sos) if x['team'] == real_team), None)
    total_ranked = len(all_sos)

    # 3. Print Header
    label = "OUT-OF-CONFERENCE" if non_conf_only else "OVERALL"
    print(f"\n💪 SCHEDULE STRENGTH: {real_team.upper()} ({start_year}-{end_year})")
    print(f"   Filter: {label}")
    print("="*80)
    
    pct = my_sos['opp_win_pct']
    rec_str = f"{my_sos['n_games']} games"
    
    print(f"   Opponent Win %:   {pct:.1f}%")
    if my_rank:
        print(f"   Schedule Rank:    #{my_rank} of {total_ranked} (Top {my_rank/total_ranked*100:.1f}%)")
    else:
        print(f"   Schedule Rank:    N/A (Not enough games)")
        
    # 4. Gather Opponent Details for Table
    opponents = []
    for nbr in G.neighbors(real_team):
        history = G.get_edge_data(real_team, nbr)['history']
        for g in history:
            year = g['season']
            if year < start_year or year > end_year: continue
            
            if non_conf_only:
                h_conf = g.get('home_conf')
                a_conf = g.get('away_conf')
                if h_conf and a_conf:
                     if data.normalize_conf_name(h_conf) == data.normalize_conf_name(a_conf):
                        continue
            
            # Determine Match Result
            if g.get('home_score') is not None:
                if g['home'] == real_team:
                    us, them = g['home_score'], g['away_score']
                else:
                    us, them = g['away_score'], g['home_score']
                
                if us > them: res = f"W {us}-{them}"
                elif them > us: res = f"L {us}-{them}"
                else: res = f"T {us}-{them}"
            else:
                res = "N/A"

            s = data.get_team_stats(nbr, year, stats_db)
            opponents.append({
                'name': nbr, 
                'year': year, 
                'stats': s,
                'result': res
            })

    # Sort by Difficulty (Rank first, then Win %)
    opponents.sort(key=lambda x: (x['stats']['rank'] if x['stats']['rank'] else 999, -x['stats']['pct']))
    
    print(f"\n💎 TOUGHEST OPPONENTS FACED")
    print(f"{'Year':<6} | {'Opponent':<20} | {'Opp Rec':<8} | {'Rank':<5} | {'Result'}")
    print("-" * 65)
    for o in opponents[:20]:
        r = o['stats']
        rank_str = f"#{r['rank']}" if r['rank'] else "-"
        rec_str = f"{r['w']}-{r['l']}"
        print(f"{o['year']:<6} | {o['name']:<20} | {rec_str:<8} | {rank_str:<5} | {o['result']}")

def print_sos_leaderboard(G, start_year, end_year, non_conf_only):
    stats_db = data.load_season_stats()
    if not stats_db:
        print("[ERROR] No stats DB found. Run build_stats_db.py first.")
        return

    label = "OUT-OF-CONFERENCE" if non_conf_only else "OVERALL"
    print(f"\n📈 SCHEDULE STRENGTH LEADERBOARD ({start_year}-{end_year})")
    print(f"   Filter: {label}")
    print("="*65)
    
    results = []
    nodes = list(G.nodes())
    total = len(nodes)
    
    print(f"   Analyzing {total} teams...", end='\r')
    
    for i, team in enumerate(nodes):
        if i % 50 == 0: print(f"   Analyzing {i}/{total} teams...", end='\r')
        
        sos = calculate_sos(G, team, start_year, end_year, non_conf_only, stats_db)
        if sos and sos['n_games'] >= 3:
            results.append({
                'team': team,
                'sos': sos['opp_win_pct'],
                'games': sos['n_games'],
                'ranked': sos['n_ranked']
            })
            
    results.sort(key=lambda x: x['sos'], reverse=True)
    
    print(f"\n{'Rank':<4} | {'Team':<25} | {'Opp Win %':<10} | {'Gms':<5} | {'Ranked Opps'}")
    print("-" * 75)
    
    for i, r in enumerate(results[:50]): # Top 50
        print(f"{i+1:<4} | {r['team']:<25} | {r['sos']:.1f}%      | {r['games']:<5} | {r['ranked']}")

# --- STANDARD STATS FUNCTIONS ---

def print_conference_stats(G, conf_1_teams, conf_1_name, conf_2_teams=None, conf_2_name=None, aggregate=False):
    # MODE A: CONFERENCE VS CONFERENCE
    if conf_2_teams:
        print(f"\n🏟️  CONFERENCE SHOWDOWN: {conf_1_name} vs {conf_2_name}")
        print("="*65)
        
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
                    pts_t1 = 0
                    pts_t2 = 0
                    
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

        win_pct = (total_c1_wins / total_games) * 100 if total_games > 0 else 0.0
        print(f"📊 AGGREGATE RECORD")
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
    
    # MODE B: SINGLE CONFERENCE REPORT
    else:
        print(f"\n🏆 CONFERENCE REPORT: {conf_1_name}")
        print(f"(Performance of current/historical {conf_1_name} members during selected timeframe)")
        print("="*65)
        
        leaderboard = []
        total_conf_wins = 0
        total_conf_games = 0
        
        for t in conf_1_teams:
            if not G.has_node(t): continue
            
            wins, losses, ties = 0, 0, 0
            pf, pa = 0, 0
            
            for nbr in G.neighbors(t):
                history = G.get_edge_data(t, nbr)['history']
                for g in history:
                    if g.get('home_score') is None: continue
                    if g['home'] == t: s1, s2 = g['home_score'], g['away_score']
                    else: s1, s2 = g['away_score'], g['home_score']
                    pf += s1
                    pa += s2
                    if s1 > s2: wins += 1
                    elif s2 > s1: losses += 1
                    else: ties += 1
            
            total_games = wins + losses + ties
            if total_games == 0: continue
            
            win_pct = (wins / total_games) * 100
            leaderboard.append({'team': t, 'w': wins, 'l': losses, 't': ties, 'pct': win_pct, 'diff': pf - pa})
            total_conf_wins += wins
            total_conf_games += total_games

        leaderboard.sort(key=lambda x: x['pct'], reverse=True)
        
        if aggregate:
            print(f"📊 AGGREGATE STATS (All Members)")
            print(f"   Combined Record: {total_conf_wins}-{total_conf_games - total_conf_wins}")
            if total_conf_games > 0:
                print(f"   Combined Win %:  {(total_conf_wins/total_conf_games)*100:.1f}%")
            if leaderboard:
                best, worst = leaderboard[0], leaderboard[-1]
                print(f"\n🌟 TOP PERFORMER:    {best['team']} ({best['w']}-{best['l']}-{best['t']}, {best['pct']:.1f}%)")
                print(f"📉 LOWEST PERFORMER: {worst['team']} ({worst['w']}-{worst['l']}-{worst['t']}, {worst['pct']:.1f}%)")
        else:
            print(f"{'Team':<25} | {'Record':<10} | {'Win %':<6} | {'Diff':<6}")
            print("-" * 65)
            for s in leaderboard:
                rec_str = f"{s['w']}-{s['l']}-{s['t']}"
                print(f"{s['team']:<25} | {rec_str:<10} | {s['pct']:.1f}%  | {s['diff']:+}")

def print_team_stats(G, centroid, non_conf_only=False):
    real_centroid = utils.resolve_team_name(G, centroid)
    if not real_centroid: return
    
    label = "OUT-OF-CONFERENCE" if non_conf_only else "HISTORICAL"
    print(f"\n📊 {label} STATS FOR: {real_centroid.upper()}")
    
    stats = []
    for opponent in G.neighbors(real_centroid):
        edge_data = G.get_edge_data(real_centroid, opponent)
        history = edge_data['history']
        valid_games = []
        total_diff = 0
        
        for g in history:
            if g.get('home_score') is None or g.get('away_score') is None: continue
            
            if non_conf_only:
                h_conf = g.get('home_conf')
                a_conf = g.get('away_conf')
                if h_conf and a_conf:
                    if data.normalize_conf_name(h_conf) == data.normalize_conf_name(a_conf):
                        continue

            valid_games.append(g)
            diff = (g['home_score'] - g['away_score']) if g['home'] == real_centroid else (g['away_score'] - g['home_score'])
            total_diff += diff
            
        count = len(valid_games)
        if count > 0:
            stats.append({
                'opponent': opponent, 'count': count,
                'total_diff': total_diff, 'avg_diff': total_diff / count,
                'last_met': edge_data['last_met'] 
            })

    stats.sort(key=lambda x: x['count'], reverse=True)
    
    print(f"\n🏆 MOST PLAYED {label} OPPONENTS")
    print(f"{'Opponent':<25} | {'Games':<5} | {'Tot Diff':<8} | {'Last Met'}")
    print("-" * 65)
    for s in stats[:10]:
        sign = "+" if s['total_diff'] > 0 else ""
        print(f"{s['opponent']:<25} | {s['count']:<5} | {sign}{s['total_diff']:<8} | {s['last_met']}")

    significant = [s for s in stats if s['count'] >= 3]
    if significant:
        significant.sort(key=lambda x: x['avg_diff'], reverse=True)
        print(f"\n🔥 DOMINANT {label} MATCHUPS (Best Avg Margin, Min 3 Games)")
        for s in significant[:3]:
            print(f"   vs {s['opponent']:<20}: +{s['avg_diff']:.1f} ppg")
        significant.sort(key=lambda x: x['avg_diff'])
        print(f"\n❄️ TOUGHEST {label} OPPONENTS (Worst Avg Margin, Min 3 Games)")
        for s in significant[:3]:
            print(f"   vs {s['opponent']:<20}: {s['avg_diff']:.1f} ppg")

def analyze_connection(G, centroid, target):
    real_centroid = utils.resolve_team_name(G, centroid)
    real_target = utils.resolve_team_name(G, target)
    if not real_centroid or not real_target:
        print("[ERROR] Teams not found.")
        return

    if G.has_edge(real_centroid, real_target):
        history = G.get_edge_data(real_centroid, real_target)['history']
        stats = {'w': 0, 'l': 0, 't': 0}
        for g in history:
            if g.get('home_score') is None: continue
            s1, s2 = (g['home_score'], g['away_score']) if g['home'] == real_centroid else (g['away_score'], g['home_score'])
            if s1 > s2: stats['w'] += 1
            elif s2 > s1: stats['l'] += 1
            else: stats['t'] += 1
        
        last = history[-1]
        res = f"{last['home']} {last['home_score']}-{last['away_score']} {last['away']}"
        print(f"\n✅ MATCHUP FOUND: {real_centroid} vs {real_target}")
        print("-" * 60)
        print(f"   Record: {stats['w']}-{stats['l']}-{stats['t']}")
        print(f"   Last:   {last['season']} ({res})")
    else:
        try:
            path = nx.shortest_path(G, source=real_centroid, target=real_target)
            print(f"\n🔗 Connection Chain ({len(path)-1} Degrees):")
            for i in range(len(path) - 1):
                t1, t2 = path[i], path[i+1]
                print(f"   {i+1}. {t1} played {t2} ({G.get_edge_data(t1, t2)['last_met']})")
        except:
            print("   No connection found.")

def list_unplayed(G, centroid, universe_teams):
    real = utils.resolve_team_name(G, centroid)
    if not real: return
    played = set(G.neighbors(real))
    valid = {t for t in universe_teams if G.has_node(t)}
    never = sorted(list(valid - played - {real}))
    print(f"\n🚫 {real} has never played the following {len(never)} teams (in selection):")
    if never:
        col_width = max(len(t) for t in never) + 2
        for i in range(0, len(never), 3):
            print("".join(word.ljust(col_width) for word in never[i:i+3]))

def print_league_diameter(G):
    if not nx.is_connected(G):
        G = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    print(f"\n📏 LEAGUE DIAMETER: {nx.diameter(G)} DEGREES")

def print_overall_stats(G):
    print("\n🌍 LEAGUE STATS...")
    matchups = sorted([{'m': f"{u} vs {v}", 'c': len(d['history'])} for u, v, d in G.edges(data=True)], key=lambda x: x['c'], reverse=True)
    print(f"\n🏛️ MOST PLAYED RIVALRIES")
    for m in matchups[:5]: print(f"{m['m']:<40} | {m['c']} games")

# --- MAIN ---
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
    
    # LOAD
    games = data.load_games_data()
    if args.start or args.end:
        print(f"[INFO] Timeframe Filter: {start_year}-{end_year}")
        games = [g for g in games if start_year <= g['season'] <= end_year]
        print(f"       Games reduced to {len(games)}")

    # GRAPH
    div_filter = data.get_team_filter(args.div)
    G = graph.build_graph(games, fbs_filter_set=div_filter)
    print(f"[INFO] Graph built with {G.number_of_nodes()} teams.")

    # ROUTER
    if args.conf:
        c1 = args.conf[0]
        c1_teams = data.get_teams_in_conference_range(c1, start_year, end_year)
        c2_teams = None
        c2 = None
        if len(args.conf) > 1:
            c2 = args.conf[1]
            c2_teams = data.get_teams_in_conference_range(c2, start_year, end_year)
        print_conference_stats(G, c1_teams, c1, c2_teams, c2, args.aggregate)

    elif args.centroid:
        cmd = args.centroid.lower()
        if cmd == "overall":
            if args.target == "sos":
                print_sos_leaderboard(G, start_year, end_year, args.non_conf)
            elif args.target == "diameter":
                print_league_diameter(G)
            else:
                print_overall_stats(G)
        
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
        print("  python3 main.py --conf Big12 --start 1996 --end 2000")
        print("  python3 main.py --conf Big12 FCS --start 2010 --end 2020")