# CFB Matchups & Advanced Analytics

A robust Python-based analytics engine for College Football history. This tool uses graph theory (NetworkX) and the CollegeFootballData API to generate advanced metrics (Strength of Record, Strength of Schedule), visualize connection chains between teams, and analyze historical matchups.

## Project Structure

```text
cfb-matchups/
├── main.py                  # Primary entry point (The "Traffic Controller")
├── config.py                # Configuration file (API Keys)
├── data.py                  # Central data loader
├── graph.py                 # Graph construction logic
├── utils.py                 # Helper functions
│
├── analysis/                # Core Logic Modules
│   ├── stats_sor.py         # Advanced Strength of Record (Asymmetric Logic)
│   ├── stats_sos.py         # Weighted Strength of Schedule
│   ├── stats_standard.py    # Conference & Historical Reports
│   └── graph_analysis.py    # Connection Chains & Shortest Paths
│
├── scripts/                 # Maintenance & Setup
│   ├── build_teams_db.py    # Fetches team metadata (Divisions, Conferences)
│   ├── build_stats_db.py    # Pre-calculates season-level W-L records
│   └── build_membership_db.py # (Optional) Conference lineage tools
│
└── data/                    # JSON/CSV Cache Storage
    ├── cfb_games_cache.json
    ├── cfb_teams_cache.json
    └── season_stats.json
```
## Setup & Installation
### 1. Prerequisites
 * Python 3.9+
 * A free API Key from CollegeFootballData.com
### 2. Install Dependencies
```Bash
pip install cfbd networkx pandas urllib3
```
### 3. Configuration
Open `config.py` and add your API key:
```Python
API_KEY = "your_cfbd_api_key_here"
```
### 4. Initialize Data
Before running analysis, you must populate the local cache. Run these scripts in order:

**Step A: Build Team Database** Fetches active FBS/FCS/D2/D3 affiliations.
```Bash
python3 scripts/build_teams_db.py
```
**Step B: Build Stats Database** Pre-calculates win/loss records for ranking purposes.
```Bash
python3 scripts/build_stats_db.py
```
*(Note: Ensure you have populated data/cfb_games_cache.json with your game history data first)*
## Features & Commands
All commands are run via `main.py`.
### 1. Strength of Record (SOR)
An advanced "resume evaluator" that grades every game played.
* Factors: Win/Loss, Margin of Victory (capped), Defensive Efficiency (vs opponent average), Location (Home/Away), and Division Disparity.
* Asymmetric Logic: Playing "down" (FBS vs FCS) offers small rewards for winning, but massive penalties for losing.
* Minimum Games: Teams must play 10 games to qualify for the leaderboard.

**Global Leaderboard:**
```Bash
python3 main.py overall sor --start 2024 --end 2024 --div all
```
**Individual Team Report:** See the specific grades for every game a team played.
```Bash
python3 main.py "Oregon" sor --start 2024 --end 2024
```
### 2. Strength of Schedule (SOS)

Calculates the weighted winning percentage of opponents.
* Weights: FBS (1.0), FCS (0.6), D2 (0.4), D3 (0.2).
```Bash
# Global Leaderboard (FBS Only)
python3 main.py overall sos --start 2024 --end 2024 --div fbs

# Specific Team Report
python3 main.py "Ohio State" sos --start 2015 --end 2024
```
### 3. Connection Chains

Find the shortest path of games connecting two teams ("Degrees of Kevin Bacon").
* Output: Shows the exact year, score, and series record for every link in the chain.
```Bash
# How many degrees separate Oregon and a random D3 school?
python3 main.py "Oregon" "Mount Union"
```
### 4. Conference Reports
Analyze internal conference standings or head-to-head showdowns between conferences.
```Bash
# Internal Report (Pac-12 History)
python3 main.py --conf "Pac-12" --start 2000 --end 2023

# Conference Showdown (SEC vs Big Ten)
python3 main.py --conf "SEC" "Big Ten" --start 2010 --end 2020
```
### 5. Historical Stats
Get a quick summary of a team's most played opponents.
```Bash
python3 main.py "Michigan" stats
```

## Historical Lineage Logic
This tool doesn't just look up current conference affiliation; it understands history.

* **Conference Lineage:** Querying `--conf "Big 12" --start 1980` automatically finds teams from the **Big Eight** (pre-1996).

* **Partial Merges:** It correctly handles complex splits. For example, asking for the **Big 12** in 1990 will include **Texas** (SWC) but exclude **Rice** (SWC), respecting the specific teams that formed the modern conference.

* **Conference vs Conference:** You can compare leagues across eras (e.g., SEC vs Big Ten in the 1990s).

## Troubleshooting

### Missing or Stale Data
If you see errors like `[WARN] No members found` or missing stats, your local cache might be out of sync.

### To reset everything:

```Bash
# 1. Delete all cached data
rm data/cfb_games_cache.json
rm data/season_stats.json
rm data/cfb_teams_cache.json

# 2. Rebuild Team Database (Requires API Key)
python3 scripts/build_teams_db.py

# 3. Download fresh game history (Run any command)
python3 main.py Oregon stats

# 4. Rebuild Membership & Stats
python3 scripts/build_membership_db.py
python3 scripts/build_stats_db.py
```
## Command Flags
<table>
    <tr>
        <td>Flag</td>
        <td>Description</td>
        <td>Example</td>
    </tr>
    <tr>
        <td><code>--start</code></td>
        <td>Filter games starting from this year.</td>
        <td><code>--start 1990</code></td>
    </tr>
    <tr>
        <td><code>--end</code></td>
        <td>Filter games up to this year.</td>
        <td><code>--end 2024</code></td>
    </tr>
    <tr>
        <td><code>--div</code></td>
        <td>Filter teams by division (fbs, fcs, ii, iii, all).</td>
        <td><code>--div fbs fcs</code></td>
    </tr>
    <tr>
        <td><code>--non-conf</code></td>
        <td>Only analyze non-conference games.</td>
        <td><code>--non-conf</code></td>
    </tr>
    <tr>
        <td><code>--aggregate</code></td>
        <td>Combine stats for conference reports.</td>
        <td><code>--aggregate</code></td>
    </tr>
 </table>

## Algorithm Details
### SOR (Strength of Record) Logic
The SOR engine calculates a Game Grade (approx -100 to +150) for every matchup:

1. Base Score: Win (100), Tie (50), Loss (0).

2. MOV: Margin of victory points added (capped at 30).

3. Defense: Bonus points for holding opponents below their scoring average.

4. Multipliers:
    * Road Win: 1.1x boost.
    * Division: Wins against lower divisions are dampened (0.5x). Losses to lower divisions are amplified (up to 1.7x).

### SOS (Strength of Schedule) Logic
Standard Opponent Win % is flawed because beating a 10-0 D3 team isn't the same as beating a 10-0 FBS team. We apply **Division Weights** to normalize records before averaging them.

* FBS Opponent: 1.0 (Full Value)

* FCS Opponent: 0.6 (Partial Value)

* Division II Opponent: 0.4

* Division III Opponent: 0.2

This ensures that a schedule loaded with lower-division cupcakes is rightfully penalized in the rankings, while still giving credit for playing strong teams at any level.