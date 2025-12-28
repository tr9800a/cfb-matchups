import data
import utils

# --- TIER LABELS ---
TIER_LABELS = {
    1: "P4",       # Power 4 (FBS)
    2: "G5",       # Group of 5 (FBS)
    3: "FCS Pwr",  # FCS Power Conferences
    4: "FCS Std",  # FCS Standard
    5: "D2 Pwr",   # D2 Power
    6: "D2 Std",   # D2 Standard
    7: "D3 Pwr",   # D3 Power
    8: "D3 Std"    # D3 Standard / NAIA / Other
}

# --- TIER CONFIGURATION ---
TIER_DEFAULTS = {
    'fbs': 2, 'fcs': 4, 'ii': 6, 'iii': 8, 'unknown': 8
}

# Teams that are Tier 1 (P4) even if they are Independent
# This prevents UMass/UConn from being T1, while keeping ND/1980s Miami T1.
POWER_INDEPENDENTS = {
    'Notre Dame', 'Penn State', 'Miami', 'Florida State', 'Syracuse', 
    'Pittsburgh', 'Boston College', 'West Virginia', 'Virginia Tech', 
    'South Carolina', 'BYU'
}

CONF_TIER_MAP = {
    # --- TIER 1: POWER 4 ---
    'SEC': 1, 'Big Ten': 1, 'Big 12': 1, 'ACC': 1, 'Pac-12': 1,
    'Southeastern Conference': 1, 'Big Ten Conference': 1, 'Atlantic Coast Conference': 1,
    'Pac-10': 1, 'SWC': 1, 'Big Eight': 1, 
    # Note: 'FBS Independents' is now handled via default + name check
    
    # --- TIER 2: G5 ---
    'American Athletic': 2, 'Mountain West': 2, 'Sun Belt': 2, 'MAC': 2, 'Conference USA': 2,
    'Mid-American': 2, 'FBS Independents': 2, # Default Independents to G5
    
    # --- TIER 3: FCS POWER ---
    'Missouri Valley': 3, 'MVFC': 3, 'Big Sky': 3, 'CAA': 3, 'Colonial': 3, 
    'Southern': 3, 'SoCon': 3, 'Southland': 3, 'Ivy': 3,
    
    # --- TIER 5: D2 POWER ---
    'GLIAC': 5, 'Gulf South': 5, 'MIAA': 5, 'PSAC': 5, 'Lone Star': 5,
    
    # --- TIER 7/8: D3 POWER & OTHERS ---
    'WIAC': 7, 'OAC': 7, 'American Southwest': 7, 'CCIW': 7,
    'NACC': 8, 'NEWMAC': 8, 
    'Centennial': 7, 'Empire 8': 7, 'NJAC': 8, 'ODAC': 8, 'Liberty League': 8
}

# STARTING STRENGTH (Pass 0)
TIER_WEIGHTS = {
    1: 1.0, 2: 0.8, 3: 0.6, 4: 0.4, 5: 0.3, 6: 0.2, 7: 0.15, 8: 0.05
}

# TIER BASELINE PENALTY
TIER_PENALTIES = {
    1: 0, 2: -15, 3: -45, 4: -65, 5: -85, 6: -105, 7: -125, 8: -145
}

def get_team_tier(team_name, conf, div):
    # 1. Historical Power Independent Check
    if conf == 'FBS Independents' or conf == 'Independent':
        if team_name in POWER_INDEPENDENTS:
            return 1
    
    # 2. Modern Notre Dame Override (Always T1)
    if team_name == 'Notre Dame': return 1

    # 3. Pac-2 Override (2024+)
    if team_name in ['Oregon State', 'Washington State'] and div == 'fbs': return 2
    
    if conf:
        if conf in CONF_TIER_MAP: return CONF_TIER_MAP[conf]
        # Partial match safety check
        unsafe_keys = {'ACC', 'MAC', 'SEC', 'CAA', 'OAC'} 
        for k, tier in CONF_TIER_MAP.items():
            if k in unsafe_keys: continue 
            if k in conf: return tier
            
    return TIER_DEFAULTS.get(div, 8)

def get_game_score(g, side):
    if side == 'home':
        return g.get('home_points') if g.get('home_points') is not None else g.get('home_score')
    else:
        return g.get('away_points') if g.get('away_points') is not None else g.get('away_score')

def calculate_complex_sor(G, start_year, end_year, stats_db, target_team=None, start_week=None, end_week=None):
    label = f"Team: {target_team}" if target_team else "Global Leaderboard"
    print(f"   [SOR] Analyzing {G.number_of_edges()} games ({label})...", end='\r')
    
    # PHASE 1: METADATA
    team_meta = {}
    for team in G.nodes():
        confs = []
        div = 'unknown'
        for nbr in G.neighbors(team):
            for g in G[team][nbr]['history']:
                if start_year <= g['season'] <= end_year:
                    if g.get('home_team') == team or g.get('home') == team:
                        confs.append(g.get('home_conference'))
                        if g.get('home_classification'): div = g.get('home_classification')
                    else:
                        confs.append(g.get('away_conference'))
                        if g.get('away_classification'): div = g.get('away_classification')
        
        primary_conf = max(set(confs), key=confs.count) if confs else "Unknown"
        tier = get_team_tier(team, primary_conf, div)
        team_meta[team] = {'div': div, 'conf': primary_conf, 'tier': tier}

    # PHASE 2: RECURSIVE SCORING
    current_ratings = {}
    final_results = []
    ITERATIONS = 2
    
    for i in range(ITERATIONS):
        is_final_pass = (i == ITERATIONS - 1)
        
        # A. OPPONENT STRENGTH
        team_strength_map = {}
        for team in G.nodes():
            opp_values = []
            for nbr in G.neighbors(team):
                has_game = False
                history = G[team][nbr]['history']
                for g in history:
                    if start_year <= g['season'] <= end_year: has_game = True
                if not has_game: continue

                if i == 0:
                    val = TIER_WEIGHTS.get(team_meta[nbr]['tier'], 0.1)
                else:
                    prev_sor = current_ratings.get(nbr, 0)
                    val = max(0.01, min(1.0, (prev_sor + 50) / 150.0))
                
                opp_values.append(val)
            
            team_strength_map[team] = sum(opp_values) / len(opp_values) if opp_values else 0.0

        # B. GAME GRADING
        pass_results = []
        loop_nodes = [target_team] if (target_team and is_final_pass) else G.nodes()
        
        for team in loop_nodes:
            if not G.has_node(team): continue
            
            game_grades = []
            detailed_games = []
            wins=0; losses=0; ties=0; point_diff=0
            
            my_tier = team_meta[team]['tier']
            
            for nbr in G.neighbors(team):
                history = G[team][nbr]['history']
                opp_tier = team_meta[nbr]['tier']
                
                for g in history:
                    if g['season'] < start_year or g['season'] > end_year: continue
                    if start_week is not None and g.get('week', 0) < start_week: continue
                    if end_week is not None and g.get('week', 99) > end_week: continue
                    
                    h_score = get_game_score(g, 'home')
                    a_score = get_game_score(g, 'away')
                    if h_score is None or a_score is None: continue
                    
                    is_home = (g.get('home_team') == team or g.get('home') == team)
                    us = h_score if is_home else a_score
                    them = a_score if is_home else h_score
                    
                    margin = us - them
                    point_diff += margin
                    if us > them: wins += 1
                    elif them > us: losses += 1
                    else: ties += 1
                    
                    # --- SCORING ENGINE ---
                    capped_margin = max(min(margin, 28), -28)
                    perf_ratio = 50 + (capped_margin * (50/28))
                    
                    opp_strength = team_strength_map.get(nbr, 0.1)
                    tier_diff = opp_tier - my_tier
                    game_value_mult = 1.0
                    
                    if margin > 0:
                        if tier_diff > 0: # I am better
                            game_value_mult = max(0.1, 1.0 - (tier_diff * 0.12))
                        elif tier_diff < 0: # I am worse
                            game_value_mult = 1.0 + (abs(tier_diff) * 0.3)
                    else:
                        if tier_diff < 0: # I lost to better team
                            game_value_mult = max(0.5, 1.0 - (abs(tier_diff) * 0.1))
                        elif tier_diff > 0: # I lost to worse team
                            game_value_mult = 1.0 + (tier_diff * 0.5)

                    loc_mult = 1.1 if (not is_home and margin > 0) else 1.0
                    
                    if margin >= 0:
                        final_grade = perf_ratio * game_value_mult * loc_mult
                    else:
                        final_grade = -1 * (100 - perf_ratio) * game_value_mult

                    game_grades.append(final_grade)
                    
                    if target_team and is_final_pass:
                        t_label = TIER_LABELS.get(opp_tier, f"T{opp_tier}")
                        detailed_games.append({
                            'opp': nbr, 'year': g['season'],
                            'result': f"{'W' if us>them else 'L'} {us}-{them}",
                            'grade': final_grade,
                            'mods': f"Str:{opp_strength:.2f} Tier:{t_label}({game_value_mult:.2f}x)",
                        })

            if game_grades:
                avg_sor = sum(game_grades) / len(game_grades)
                tier_penalty = TIER_PENALTIES.get(my_tier, -145) 
                total_score = avg_sor + tier_penalty
                
                pass_results.append({
                    'team': team, 
                    'sor': total_score, 
                    'games': len(game_grades), 
                    'w': wins, 'l': losses, 't': ties,
                    'diff': point_diff,
                    'tier': my_tier,
                    'div': team_meta[team]['div'],
                    'details': detailed_games
                })
        
        for r in pass_results:
            current_ratings[r['team']] = r['sor']
            
        if is_final_pass:
            final_results = pass_results

    return final_results

def print_sor_leaderboard(sor_data, start_year, end_year):
    # 1. Sort
    sor_data.sort(key=lambda x: x['sor'], reverse=True)
    
    # 2. Assign Rank (First step!)
    rank = 1
    for r in sor_data:
        r['rank'] = rank
        rank += 1
        
    # 3. Filter for display
    valid_data = [x for x in sor_data if x['games'] >= 6]
    
    print(f"\n[SOR] TOP-TO-BOTTOM RANKING ({start_year}-{end_year})")
    print(f"      System: 8-Tier Hierarchy (Tier Penalty Applied)")
    print("="*90)
    
    # --- TIER EXTREMES SECTION ---
    tier_groups = {}
    for r in valid_data:
        t = r['tier']
        if t not in tier_groups: tier_groups[t] = []
        tier_groups[t].append(r)
        
    sorted_tiers = sorted(tier_groups.keys())
    
    print(f"      TIER EXTREMES (Best & Worst by Tier)")
    print(f"{'Tier':<8} | {'Rank':<4} | {'Best Team':<25} | {'Score':<6} || {'Rank':<4} | {'Worst Team':<25} | {'Score':<6}")
    print("-" * 105)
    
    for t in sorted_tiers:
        teams = tier_groups[t]
        best = teams[0]
        worst = teams[-1]
        t_label = TIER_LABELS.get(t, f"T{t}")
        
        # New Format: Team (W-L)
        best_name = f"{best['team']} ({best['w']}-{best['l']})"
        worst_name = f"{worst['team']} ({worst['w']}-{worst['l']})"
        
        print(f"{t_label:<8} | {best['rank']:<4} | {best_name:<25} | {best['sor']:<6.1f} || {worst['rank']:<4} | {worst_name:<25} | {worst['sor']:<6.1f}")

    print("="*105)
    print(f"{'Rank':<4} | {'Team':<25} | {'Tier':<8} | {'SOR':<8} | {'Rec':<8} | {'Diff':<5}")
    print("-" * 105)
    
    for r in valid_data[:50]:
        rec_str = f"{r['w']}-{r['l']}"
        diff_str = f"{r['diff']:+}"
        tier_str = TIER_LABELS.get(r['tier'], f"T{r['tier']}")
        print(f"{r['rank']:<4} | {r['team']:<25} | {tier_str:<8} | {r['sor']:<8.1f} | {rec_str:<8} | {diff_str:<5}")

def print_team_sor_report(sor_data, team_name):
    if not sor_data: return
    data = sor_data[0]
    games = sorted(data['details'], key=lambda x: x['year'], reverse=True)
    rec_str = f"{data['w']}-{data['l']}"
    t_label = TIER_LABELS.get(data['tier'], f"T{data['tier']}")
    
    print(f"\n[SOR] RECORD BREAKDOWN: {team_name.upper()}")
    print(f"      Score: {data['sor']:.2f} | Tier: {t_label}")
    print(f"      Record: {rec_str} | Diff: {data['diff']:+}")
    print("="*95)
    print(f"{'Year':<6} | {'Opponent':<20} | {'Res':<8} | {'Grade':<8} | {'Modifiers'}")
    print("-" * 95)
    for g in games:
        print(f"{g['year']:<6} | {g['opp']:<20} | {g['result']:<8} | {g['grade']:<8.1f} | {g['mods']}")