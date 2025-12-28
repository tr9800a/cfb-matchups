import networkx as nx
import utils

def get_game_score(g, side):
    """Safely retrieves points/score from game dict"""
    if side == 'home':
        return g.get('home_points') if g.get('home_points') is not None else g.get('home_score')
    else:
        return g.get('away_points') if g.get('away_points') is not None else g.get('away_score')

def print_conference_stats(G, c1_teams, c1_name, c2_teams=None, c2_name=None, aggregate=False):
    """
    Analyzes matchups between two conferences (e.g. SEC vs Big Ten).
    """
    if not c2_teams:
        # Single Conference Internal Report
        print(f"\n[CONF] {c1_name} Internal Analysis")
        print("="*60)
        # (Internal logic can go here if needed later)
        return

    print(f"\n[VS] CONFERENCE SHOWDOWN: {c1_name} vs {c2_name}")
    print("="*60)
    
    matchups = []
    
    # Identify all edges between the two sets
    for t1 in c1_teams:
        if t1 not in G: continue
        for t2 in c2_teams:
            if t2 not in G: continue
            
            if G.has_edge(t1, t2):
                h = G[t1][t2]['history']
                
                # Calculate record using robust score getter
                wins = 0
                losses = 0
                ties = 0
                
                for g in h:
                    s1 = get_game_score(g, 'home') if g.get('home') == t1 or g.get('home_team') == t1 else get_game_score(g, 'away')
                    s2 = get_game_score(g, 'away') if g.get('home') == t1 or g.get('home_team') == t1 else get_game_score(g, 'home')
                    
                    if s1 is None or s2 is None: continue
                    
                    if s1 > s2: wins += 1
                    elif s2 > s1: losses += 1
                    else: ties += 1
                
                if wins + losses + ties > 0:
                    matchups.append({
                        't1': t1, 't2': t2,
                        'w': wins, 'l': losses, 't': ties,
                        'total': wins + losses + ties
                    })

    # Sort by total games played
    matchups.sort(key=lambda x: x['total'], reverse=True)
    
    # Aggregate Totals
    total_w = sum(m['w'] for m in matchups)
    total_l = sum(m['l'] for m in matchups)
    total_t = sum(m['t'] for m in matchups)
    
    print(f"HEAD-TO-HEAD TOTAL: {c1_name} {total_w} - {c2_name} {total_l} ({total_t} Ties)")
    print("-" * 60)
    
    if aggregate:
        print(f"(Aggregated View - Individual series hidden)")
    else:
        for m in matchups:
            print(f"{m['t1']:<20} vs {m['t2']:<20} | {m['w']}-{m['l']}-{m['t']}")

def print_team_stats(G, team_input, non_conf=False):
    """
    Prints standard historical stats for a single team.
    """
    team = utils.resolve_team_name(G, team_input)
    if not team:
        print(f"Team '{team_input}' not found.")
        return

    print(f"\n[STATS] Historical Summary: {team}")
    print("="*60)
    
    opponents = []
    total_w = 0
    total_l = 0
    total_t = 0
    
    for nbr in G.neighbors(team):
        history = G[team][nbr]['history']
        
        w = 0; l = 0; t = 0
        for g in history:
            if non_conf and g.get('conference_game'): continue
            
            # Robust Score Check
            is_home = (g.get('home') == team or g.get('home_team') == team)
            us = get_game_score(g, 'home') if is_home else get_game_score(g, 'away')
            them = get_game_score(g, 'away') if is_home else get_game_score(g, 'home')
            
            if us is None or them is None: continue
            
            if us > them: w += 1
            elif them > us: l += 1
            else: t += 1
            
        if w+l+t > 0:
            opponents.append({'opp': nbr, 'w': w, 'l': l, 't': t, 'total': w+l+t})
            total_w += w
            total_l += l
            total_t += t
            
    # Sort by most played
    opponents.sort(key=lambda x: x['total'], reverse=True)
    
    print(f"Overall Record: {total_w}-{total_l}-{total_t}")
    print("-" * 60)
    print(f"{'Opponent':<25} | {'Rec':<10} | {'Gms'}")
    print("-" * 60)
    
    for o in opponents[:25]: # Top 25 most played
        rec = f"{o['w']}-{o['l']}-{o['t']}"
        print(f"{o['opp']:<25} | {rec:<10} | {o['total']}")