import data
import utils

def calculate_complex_sor(G, start_year, end_year, stats_db, target_team=None):
    label = f"Team: {target_team}" if target_team else "Global Leaderboard"
    print(f"   [SOR] Analyzing {G.number_of_edges()} games ({label})...", end='\r')
    
    # --- PASS 1: TEAM BASELINES ---
    team_baselines = {}
    for team in G.nodes():
        points_scored = 0
        points_allowed = 0
        games_played = 0
        
        for nbr in G.neighbors(team):
            history = G.get_edge_data(team, nbr)['history']
            for g in history:
                if g['season'] < start_year or g['season'] > end_year: continue
                if g.get('home_score') is None: continue
                
                games_played += 1
                if g['home'] == team:
                    points_scored += g['home_score']
                    points_allowed += g['away_score']
                else:
                    points_scored += g['away_score']
                    points_allowed += g['home_score']
        
        div = data.get_team_classification(team)
        if games_played > 0:
            team_baselines[team] = {'avg_off': points_scored / games_played, 'div': div}
        else:
            team_baselines[team] = {'avg_off': 25, 'div': div}

    # --- PASS 2: OPPONENT STRENGTH ---
    team_strength = {}
    div_weights = {'fbs': 1.0, 'fcs': 0.6, 'ii': 0.4, 'iii': 0.2, 'unknown': 0.5}
    
    for team in G.nodes():
        opp_scores = []
        for nbr in G.neighbors(team):
            pcts = []
            for y in range(start_year, end_year + 1):
                s = data.get_team_stats(nbr, y, stats_db)
                if s['w'] + s['l'] > 0: pcts.append(s['pct'])
            
            if pcts:
                avg_win_pct = sum(pcts) / len(pcts)
                wgt = div_weights.get(team_baselines.get(nbr, {}).get('div', 'unknown'), 0.5)
                opp_scores.append(avg_win_pct * wgt)
        
        team_strength[team] = sum(opp_scores) / len(opp_scores) if opp_scores else 0.0

    # --- PASS 3: GAME GRADING ---
    # Base Multipliers (0.0 to 1.0)
    abs_div_mults = {'fbs': 1.0, 'fcs': 0.7, 'ii': 0.5, 'iii': 0.3, 'unknown': 0.5}
    
    sor_results = []
    loop_nodes = [target_team] if target_team else G.nodes()
    
    for team in loop_nodes:
        if not G.has_node(team): continue
        game_grades = []
        detailed_games = []
        
        wins = 0
        losses = 0
        ties = 0
        point_diff = 0
        
        for nbr in G.neighbors(team):
            history = G.get_edge_data(team, nbr)['history']
            for g in history:
                if g['season'] < start_year or g['season'] > end_year: continue
                if g.get('home_score') is None: continue
                
                # Logic
                is_home = (g['home'] == team)
                us = g['home_score'] if is_home else g['away_score']
                them = g['away_score'] if is_home else g['home_score']
                opp_baseline = team_baselines.get(nbr, {'avg_off': 25, 'div': 'fbs'})
                
                # Stats
                margin = us - them
                point_diff += margin
                if us > them: wins += 1
                elif them > us: losses += 1
                else: ties += 1
                
                # Scoring Components
                base_score = 100.0 if us > them else (50.0 if us == them else 0.0)
                capped_margin = max(min(margin, 30), -30)
                mov_score = capped_margin * 0.5
                def_score = (opp_baseline['avg_off'] - them) * 1.0
                
                # --- MODIFIERS ---
                
                # 1. Location
                loc_mult = 1.1 if (not is_home and margin > 0) else (0.9 if (is_home and margin < 0) else 1.0)
                
                # 2. Relative Division (Underdog Bonus / Bully Penalty)
                my_div = team_baselines.get(team, {}).get('div', 'fbs')
                opp_div = opp_baseline.get('div', 'fbs')
                rel_div_mult = 1.0
                if my_div == 'fbs' and opp_div != 'fbs':
                    rel_div_mult = 0.5 if margin > 0 else 0.0
                elif my_div != 'fbs' and opp_div == 'fbs':
                    rel_div_mult = 2.0 if margin > 0 else 1.0
                    
                # 3. Opponent Quality (0.5 to 1.5)
                opp_quality = 0.5 + team_strength.get(nbr, 0.0)
                
                # --- 4. ABSOLUTE DIVISION (ASYMMETRIC LOGIC) ---
                # "Easy Mode" logic: Wins are small, Losses are huge.
                div_factor = abs_div_mults.get(opp_div, 0.5)
                
                raw_grade = base_score + mov_score + def_score
                
                # If Score is Positive (Win/Good perf): Dampen it (Standard logic)
                # Example D3: +100 becomes +30
                if raw_grade >= 0:
                    final_grade = raw_grade * loc_mult * rel_div_mult * opp_quality * div_factor
                    mod_str = f"A:{div_factor}"
                
                # If Score is Negative (Loss/Bad perf): AMPLIFY it (Penalty logic)
                # Example D3: -100 becomes -170.
                # Penalty Factor = 1.0 + (1.0 - div_factor)
                # FBS (1.0) -> 1.0x (No change)
                # D3 (0.3) -> 1.7x (Huge penalty for losing in easy mode)
                else:
                    penalty_factor = 1.0 + (1.0 - div_factor)
                    final_grade = raw_grade * loc_mult * rel_div_mult * opp_quality * penalty_factor
                    mod_str = f"A:{penalty_factor}(Pen)"

                game_grades.append(final_grade)
                
                if target_team:
                    detailed_games.append({
                        'opp': nbr, 'year': g['season'],
                        'result': f"{'W' if us>them else 'L'} {us}-{them}",
                        'grade': final_grade,
                        'mods': f"L:{loc_mult} D:{rel_div_mult} Q:{opp_quality:.2f} {mod_str}",
                        'opp_div': opp_div
                    })

        if game_grades:
            avg_sor = sum(game_grades) / len(game_grades)
            sor_results.append({
                'team': team, 
                'sor': avg_sor, 
                'games': len(game_grades), 
                'w': wins,
                'l': losses,
                't': ties,
                'diff': point_diff,
                'div': team_baselines.get(team, {}).get('div', 'unknown'),
                'details': detailed_games
            })
            
    return sor_results

def print_sor_leaderboard(sor_data, start_year, end_year):
    sor_data.sort(key=lambda x: x['sor'], reverse=True)
    
    # Assign Ranks
    rank = 1
    for r in sor_data:
        r['rank'] = rank
        rank += 1
        
    valid_data = [x for x in sor_data if x['games'] >= 10]
    
    print(f"\n[SOR] MODIFIED STRENGTH OF RECORD ({start_year}-{end_year})")
    print(f"      Factors: Win%, MOV, Def Efficiency, Div Disparity, Opp Strength")
    print(f"      Min Games: 10")
    print("="*85)
    
    # Division Extremes
    div_map = {}
    for r in valid_data:
        d = r['div'].upper()
        if d not in div_map: div_map[d] = []
        div_map[d].append(r)
    
    extremes_list = []
    for d in div_map:
        teams = div_map[d]
        if teams:
            extremes_list.append(teams[0])
            if len(teams) > 1: extremes_list.append(teams[-1])
            
    unique_extremes = {t['team']: t for t in extremes_list}.values()
    sorted_extremes = sorted(unique_extremes, key=lambda x: x['rank'])
    
    if sorted_extremes:
        print(f"      DIVISION EXTREMES (Highest & Lowest Rated)")
        print(f"{'Rank':<4} | {'Team':<25} | {'Div':<5} | {'SOR Score':<10} | {'Gms':<5} | {'Rec':<8} | {'Diff'}")
        print("-" * 85)
        for r in sorted_extremes:
            rec_str = f"{r['w']}-{r['l']}"
            diff_str = f"{r['diff']:+}"
            print(f"{r['rank']:<4} | {r['team']:<25} | {r['div'].upper():<5} | {r['sor']:.2f}       | {r['games']:<5} | {rec_str:<8} | {diff_str}")
        print("="*85)

    print(f"\n[LEADERBOARD] TOP 50")
    print(f"{'Rank':<4} | {'Team':<25} | {'Div':<5} | {'SOR Score':<10} | {'Gms':<5} | {'Rec':<8} | {'Diff'}")
    print("-" * 85)
    
    for r in valid_data[:50]:
        rec_str = f"{r['w']}-{r['l']}"
        diff_str = f"{r['diff']:+}"
        print(f"{r['rank']:<4} | {r['team']:<25} | {r['div'].upper():<5} | {r['sor']:.2f}       | {r['games']:<5} | {rec_str:<8} | {diff_str}")

def print_team_sor_report(sor_data, team_name):
    if not sor_data: return
    data = sor_data[0]
    games = sorted(data['details'], key=lambda x: x['year'], reverse=True)
    rec_str = f"{data['w']}-{data['l']}"
    print(f"\n[SOR] RECORD BREAKDOWN: {team_name.upper()}")
    print(f"      Overall Score: {data['sor']:.2f}")
    print(f"      Record: {rec_str} ({data['games']} games)")
    print(f"      Point Diff: {data['diff']:+}")
    print("="*85)
    print(f"{'Year':<6} | {'Opponent':<20} | {'Div':<5} | {'Result':<10} | {'Grade':<8} | {'Modifiers'}")
    print("-" * 85)
    for g in games:
        print(f"{g['year']:<6} | {g['opp']:<20} | {g['opp_div'].upper():<5} | {g['result']:<10} | {g['grade']:<8.1f} | {g['mods']}")