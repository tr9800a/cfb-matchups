import data
import utils

def calculate_sos(G, team, start_year, end_year, non_conf_only, stats_db):
    if not G.has_node(team): return None
    opponents_faced = []
    weights = {'fbs': 1.0, 'fcs': 0.6, 'ii': 0.4, 'iii': 0.2, 'unknown': 0.5}
    
    for nbr in G.neighbors(team):
        history = G.get_edge_data(team, nbr)['history']
        for g in history:
            year = g['season']
            if year < start_year or year > end_year: continue
            if non_conf_only:
                if g.get('home_conf') and g.get('away_conf'):
                    if data.normalize_conf_name(g['home_conf']) == data.normalize_conf_name(g['away_conf']): continue

            raw_stats = data.get_team_stats(nbr, year, stats_db)
            div = data.get_team_classification(nbr)
            wgt = weights.get(div, 0.5)
            
            res = "N/A"
            if g.get('home_score') is not None:
                us, them = (g['home_score'], g['away_score']) if g['home'] == team else (g['away_score'], g['home_score'])
                res = f"W {us}-{them}" if us > them else (f"L {us}-{them}" if them > us else f"T {us}-{them}")
            
            opponents_faced.append({'name': nbr, 'year': year, 'raw': raw_stats, 'weight': wgt, 'div': div, 'game_result': res})

    if not opponents_faced: return None
    weighted_sum = sum((o['raw']['w'] / (o['raw']['w']+o['raw']['l']+o['raw']['t']) * o['weight']) for o in opponents_faced if (o['raw']['w']+o['raw']['l']+o['raw']['t']) > 0)
    valid_games = sum(1 for o in opponents_faced if (o['raw']['w']+o['raw']['l']+o['raw']['t']) > 0)
    
    if valid_games == 0: return None
    return {'weighted_score': (weighted_sum / valid_games) * 100, 'n_games': len(opponents_faced), 'n_ranked': sum(1 for o in opponents_faced if o['raw']['rank']), 'opponents': opponents_faced}

def print_sos_report(G, team_name, start_year, end_year, non_conf_only):
    real_team = utils.resolve_team_name(G, team_name)
    if not real_team: return
    stats_db = data.load_season_stats()
    if not stats_db: return
    
    my_sos = calculate_sos(G, real_team, start_year, end_year, non_conf_only, stats_db)
    if not my_sos: return

    # Rank Loop
    all_sos = []
    for node in G.nodes():
        s = calculate_sos(G, node, start_year, end_year, non_conf_only, stats_db)
        if s and s['n_games'] >= 3: all_sos.append({'team': node, 'score': s['weighted_score']})
    all_sos.sort(key=lambda x: x['score'], reverse=True)
    my_rank = next((i+1 for i, x in enumerate(all_sos) if x['team'] == real_team), None)
    
    label = "OUT-OF-CONFERENCE" if non_conf_only else "OVERALL"
    print(f"\n[SOS] SCHEDULE STRENGTH: {real_team.upper()} ({start_year}-{end_year})")
    print(f"      Filter: {label}")
    print(f"      Score: {my_sos['weighted_score']:.1f} | Rank: #{my_rank} of {len(all_sos)}")
    print("="*85)
    
    opponents = sorted(my_sos['opponents'], key=lambda x: ((x['raw']['pct'] * x['weight']), x['raw']['rank'] or 999), reverse=True)
    print(f"{'Year':<6} | {'Opponent':<20} | {'Div':<5} | {'Rec':<8} | {'Raw %':<6} | {'Result':<12}")
    print("-" * 85)
    for o in opponents[:20]:
        name = o['name'] + (f" (#{o['raw']['rank']})" if o['raw']['rank'] else "")
        print(f"{o['year']:<6} | {name:<20} | {o['div'].upper():<5} | {o['raw']['w']}-{o['raw']['l']:<6} | {o['raw']['pct']*100:<6.1f} | {o['game_result']}")

def print_sos_leaderboard(G, start_year, end_year, non_conf_only):
    stats_db = data.load_season_stats()
    results = []
    for team in G.nodes():
        sos = calculate_sos(G, team, start_year, end_year, non_conf_only, stats_db)
        if sos and sos['n_games'] >= 10: results.append({'team': team, 'score': sos['weighted_score'], 'games': sos['n_games'], 'ranked': sos['n_ranked']})
    
    results.sort(key=lambda x: x['score'], reverse=True)
    print(f"\n[LEADERBOARD] SOS ({start_year}-{end_year})")
    print("-" * 75)
    for i, r in enumerate(results[:50]):
        print(f"{i+1:<4} | {r['team']:<25} | {r['score']:.1f}       | {r['games']:<5} | {r['ranked']}")