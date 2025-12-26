import data
import utils

def print_conference_stats(G, c1_teams, c1_name, c2_teams=None, c2_name=None, aggregate=False):
    if c2_teams:
        print(f"\n[VS] CONFERENCE SHOWDOWN: {c1_name} vs {c2_name}")
        t_wins = [0, 0]
        total = 0
        matchups = []
        for t1 in c1_teams:
            if not G.has_node(t1): continue
            for t2 in c2_teams:
                if not G.has_node(t2): continue
                if G.has_edge(t1, t2):
                    h = G.get_edge_data(t1, t2)['history']
                    w = sum(1 for g in h if (g['home']==t1 and g['home_score']>g['away_score']) or (g['away']==t1 and g['away_score']>g['home_score']))
                    t_wins[0] += w; t_wins[1] += (len(h)-w); total += len(h)
                    if not aggregate: matchups.append({'m': f"{t1} vs {t2}", 'r': f"{w}-{len(h)-w}", 'l': h[-1]['season']})
        
        if total: print(f"   Record: {t_wins[0]}-{t_wins[1]} ({(t_wins[0]/total)*100:.1f}%)")
        if not aggregate:
            for m in sorted(matchups, key=lambda x: x['l'], reverse=True)[:25]:
                print(f"   {m['m']:<35} | {m['r']:<10} | {m['l']}")
    else:
        print(f"\n[REPORT] CONFERENCE REPORT: {c1_name}")
        leaderboard = []
        for t in c1_teams:
            if not G.has_node(t): continue
            w, l, t_cnt = 0, 0, 0
            for nbr in G.neighbors(t):
                for g in G.get_edge_data(t, nbr)['history']:
                    if g.get('home_score') is None: continue
                    s1, s2 = (g['home_score'], g['away_score']) if g['home']==t else (g['away_score'], g['home_score'])
                    if s1>s2: w+=1
                    elif s2>s1: l+=1
                    else: t_cnt+=1
            tot = w+l+t_cnt
            if tot: leaderboard.append({'t': t, 'p': w/tot, 'r': f"{w}-{l}-{t_cnt}"})
        
        for r in sorted(leaderboard, key=lambda x: x['p'], reverse=True):
            print(f"{r['t']:<25} | {r['r']:<10} | {r['p']*100:.1f}%")

def print_team_stats(G, centroid, non_conf_only=False):
    real = utils.resolve_team_name(G, centroid)
    if not real: return
    label = "OUT-OF-CONFERENCE" if non_conf_only else "HISTORICAL"
    print(f"\n[STATS] {label}: {real.upper()}")
    stats = []
    for nbr in G.neighbors(real):
        h = G.get_edge_data(real, nbr)['history']
        valid = []
        d = 0
        for g in h:
            if non_conf_only and g.get('home_conf') and g.get('away_conf'):
                if data.normalize_conf_name(g['home_conf']) == data.normalize_conf_name(g['away_conf']): continue
            if g.get('home_score') is not None:
                valid.append(g)
                d += (g['home_score'] - g['away_score']) if g['home']==real else (g['away_score'] - g['home_score'])
        if valid: stats.append({'op': nbr, 'c': len(valid), 'd': d, 'l': h[-1]['season']})
    
    for s in sorted(stats, key=lambda x: x['c'], reverse=True)[:10]:
        print(f"   vs {s['op']:<25}: {s['c']:<3} games ({s['d']:+4} diff) | Last: {s['l']}")