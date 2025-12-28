import argparse
import sys
from datetime import datetime
import warnings
warnings.filterwarnings("ignore", module="urllib3")
import urllib3

import data
import graph
import utils
from analysis import stats_sor, stats_sos, stats_standard, graph_analysis

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
    parser.add_argument('--start-week', type=int, default=None, help="Starting week (e.g. 1)")
    parser.add_argument('--end-week', type=int, default=None, help="Ending week (e.g. 15)")
    parser.add_argument('--include-postseason', action='store_true', help="Include postseason games in analysis")

    args = parser.parse_args()
    start_year = args.start if args.start else 1869
    end_year = args.end if args.end else datetime.now().year

    # 1. LOAD
    games = data.load_games_data()
    
    # 2. FILTER: Years
    if args.start or args.end:
        games = [g for g in games if start_year <= g['season'] <= end_year]

    # 3. FILTER: Postseason (Default Behavior)
    if not args.include_postseason:
        # We perform a safe get() in case 'season_type' is missing in very old data
        games = [g for g in games if g.get('season_type') == 'regular']
    else:
        print("[INFO] Including Postseason Games")

    # 4. GRAPH
    div_filter = data.get_team_filter(args.div)
    G = graph.build_graph(games, fbs_filter_set=div_filter)
    
    # 5. ROUTE
    if args.conf:
        c1 = args.conf[0]
        c1_teams = data.get_teams_in_conference_range(c1, start_year, end_year)
        c2 = args.conf[1] if len(args.conf) > 1 else None
        c2_teams = data.get_teams_in_conference_range(c2, start_year, end_year) if c2 else None
        stats_standard.print_conference_stats(G, c1_teams, c1, c2_teams, c2, args.aggregate)

    elif args.centroid:
        cmd = args.centroid.lower()
        stats_db = data.load_season_stats() if (args.target and args.target.lower() in ['sos', 'sor']) else None
        
        # SOR
        if args.target and args.target.lower() == "sor":
            if cmd == "overall":
                d = stats_sor.calculate_complex_sor(
                    G, start_year, end_year, stats_db, 
                    start_week=args.start_week, end_week=args.end_week
                )
                stats_sor.print_sor_leaderboard(d, start_year, end_year)
            else:
                real = utils.resolve_team_name(G, args.centroid)
                if real:
                    d = stats_sor.calculate_complex_sor(
                        G, start_year, end_year, stats_db, target_team=real,
                        start_week=args.start_week, end_week=args.end_week
                    )
                    stats_sor.print_team_sor_report(d, real)
        
        # SOS
        elif args.target and args.target.lower() == "sos":
            if cmd == "overall": stats_sos.print_sos_leaderboard(G, start_year, end_year, args.non_conf)
            else: stats_sos.print_sos_report(G, args.centroid, start_year, end_year, args.non_conf)
        
        # STANDARD
        elif args.target and args.target.lower() == "stats":
            stats_standard.print_team_stats(G, args.centroid, args.non_conf)
            
        # ECCENTRICITY (Team Diameter)
        elif args.target and args.target.lower() == "diameter":
            if cmd == "overall":
                graph_analysis.print_league_diameter(G)
            else:
                graph_analysis.print_team_eccentricity(G, args.centroid)

        elif cmd == "overall":
            if args.target == "diameter": graph_analysis.print_league_diameter(G)
            else: graph_analysis.print_overall_stats(G)
            
        elif args.target:
            graph_analysis.analyze_connection(G, args.centroid, args.target)