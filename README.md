# CFB Matchups & Advanced Analytics

A robust Python-based analytics engine for College Football history. This tool uses graph theory (NetworkX) and the CollegeFootballData API to generate advanced metrics (Strength of Record, Strength of Schedule), visualize connection chains between teams, and analyze historical matchups.

## Project Structure

```text
cfb-matchups/
├── main.py                  # Primary entry point (The "Traffic Controller")
├── config.py                # Configuration file (API Keys)
├── data.py                  # Central data loader & Compatibility patcher
├── graph.py                 # Graph construction logic
├── utils.py                 # Helper functions
│
├── analysis/                # Core Logic Modules
│   ├── stats_sor.py         # Recursive Strength of Record (8-Tier System)
│   ├── stats_sos.py         # Weighted Strength of Schedule
│   ├── stats_standard.py    # Conference & Historical Reports
│   └── graph_analysis.py    # Connection Chains & Shortest Paths, Diameter & Eccentricity
│
├── scripts/                 # Maintenance & Setup
│   ├── build_games_db.py    # Fetches full game history (1869-Present)
│   ├── repair_teams.py      # Backfills missing tier/conference data from game history
│   ├── build_stats_db.py    # Pre-calculates season-level W-L records
│   └── build_membership_db.py # (Optional) Conference lineage tools
│
└── data/                    # JSON/CSV Cache Storage
    ├── cfb_games_cache.json
    ├── cfb_teams_cache.json
    ├── conference_lineage_and_aliases_enhanced.json
    ├── membership_full.csv
    └── season_stats.json
```
## Setup & Installation
### 1. Prerequisites
 * Python 3.9+
 * A free API Key from CollegeFootballData.com

### 2. Install Dependencies
```Bash
pip install cfbd networkx pandas urllib3 tqdm
```

### 3. Configuration
Open `config.py` and add your API key:
```Python
API_KEY = "your_cfbd_api_key_here"
```

### 4. Initialize Data
Before running analysis, you must populate the local cache. **Run these scripts in this exact order:**

#### Step A: Fetch Game History
Downloads every game from 1869 to present (or specified range).
```Bash
python3 scripts/build_games_db.py
```
#### Step B: Repair Team Metadata 
**CRITICAL:** Scans game history to infer correct conferences and tiers. Without this, rankings will be inaccurate.
```Bash
python3 scripts/repair_teams.py
```
#### Step C: Build Stats Database 
Pre-calculates win/loss records for ranking purposes.
```Bash
python3 scripts/build_stats_db.py
```

## Master Command Reference
All commands are run via `main.py`

### 1. Advanced Metrics (SOR & SOS)
#### Strength of Record (SOR)
An Iterative, Top-to-Bottom resume evaluator.
```Bash
# Global Leaderboard (Top-to-Bottom)
python3 main.py overall sor --start 2024 --end 2024 --div all

# Filter for Non-Conference Only (Who played the hardest OOC schedule?)
python3 main.py overall sor --start 2024 --end 2024 --div fbs --non-conf

# Individual Team Report (Detailed Game Grades)
python3 main.py "Oregon" sor --start 2024 --end 2024
```

#### Strength of Schedule (SOS)
Weighted opponent winning percentage.
```Bash
# Global Leaderboard (FBS Only)
python3 main.py overall sos --start 2024 --end 2024 --div fbs

# Specific Team Report
python3 main.py "Ohio State" sos --start 2015 --end 2024
```

### 2. Network Topology & Chains
#### Connection Chains
Find the shortest path of games connecting two specific teams.

*Output: Shows the exact year, score, and series record for every link in the chain.*
```Bash
# How many degrees separate Oregon and a random D3 school?
python3 main.py "Oregon" "Mount Union"
```

#### League Diameter
Finds the "longest shortest path" in the entire league.
```Bash
# What is the maximum degree of separation between any two teams?
python3 main.py overall diameter --div all
```

#### Team Eccentricity
Finds the team furthest away from a specific school.
```Bash
# Who is the furthest team from Oregon?
python3 main.py "Oregon" diameter --div all
```

#### Graph Health Check
Analyze density, connectivity, and islands (disconnected teams).
```Bash
python3 main.py overall --start 2024 --div all
```

### 3. Historical Stats
#### Unplayed Matchups
Find every team in a division that a school has never played. *(Note: Running a team name without a command defaults to this report)*
```Bash
# List all FBS teams Oregon has never played
python3 main.py "Oregon" --div fbs
```

#### Standard Stats
Get a quick summary of a team's most played opponents and overall record.
```Bash
python3 main.py "Michigan" stats
```

### 4. Conference Analysis
#### Conference vs Conference
Analyze head-to-head performance between two leagues.
```Bash
# Detailed Series List
python3 main.py --conf "SEC" "Big Ten" --start 2010 --end 2020

# Aggregated W-L Record Only
python3 main.py --conf "SEC" "Big Ten" --start 2010 --end 2020 --aggregate
```

#### Internal Conference Report
Analyze internal matchups.
```Bash
python3 main.py --conf "Pac-12" --start 2000 --end 2023
```

## Command Flags
<table>
    <tr>
        <td>Flag</td>
        <td>Description</td>
        <td>Example</td>
    </tr>
    <tr>
        <td><code>--start [YEAR]</code></td>
        <td>Filter games starting from this year.</td>
        <td><code>--start 1990</code></td>
    </tr>
    <tr>
        <td><code>--end [YEAR]</code></td>
        <td>Filter games up to this year.</td>
        <td><code>--end 2024</code></td>
    </tr>
    <tr>
        <td><code>--div [DIV...]</code></td>
        <td>Filter teams by division (<code>fbs</code>, <code>fcs</code>, <code>ii</code>, <code>iii</code>, <code>all</code>). Default: <code>fbs</code></td>
        <td><code>--div fbs fcs</code></td>
    </tr>
    <tr>
        <td><code>--non-conf</code></td>
        <td>**Exclude** conference games. Useful for evaluating OOC scheduling.</td>
        <td><code>--non-conf</code></td>
    </tr>
    <tr>
        <td><code>--include-postseason</code></td>
        <td>**Include** Bowls/Playoffs. Default: Regular season only.</td>
        <td><code>--include-postseason</code></td>
    </tr>
    <tr>
        <td><code>--aggregate</code></td>
        <td>Combine stats for conference reports.</td>
        <td><code>--aggregate</code></td>
    </tr>
    <tr>
        <td><code>--start-week [N]</code></td>
        <td>Start analysis at specific week N.</td>
        <td><code>--start-week 0</code></td>
    </tr>
    <tr>
        <td><code>--end-week [N]</code></td>
        <td>End analysis at specific week N.</td>
        <td><code>--end-week 10</code></td>
    </tr>
 </table>

## Historical Lineage Logic
This tool doesn't just look up current conference affiliation; it understands history.

### Conference Lineage
Querying `--conf "Big 12" --start 1980` automatically finds teams from the **Big Eight** (pre-1996).

### Partial Merges
It correctly handles complex splits. For example, asking for the **Big 12** in 1990 will include **Texas** (SWC) but exclude **Rice** (SWC), respecting the specific teams that formed the modern conference.

### Conference vs Conference
You can compare leagues across eras (e.g., SEC vs Big Ten in the 1990s).

## Algorithm Details: The SOR Engine
The Strength of Record engine uses a complex, tier-aware algorithm to grade performance.

### 1. The 8-Tier Hierarchy
To ensure a true top-to-bottom ranking, teams are assigned a tier based on their conference and classification. Each tier applies a baseline penalty to the final score to prevent lower-division inflation.

<table>
    <tr>
        <td>Tier</td>
        <td>Label</td>
        <td>Description</td>
        <td>Penalty</td>
    </tr>
    <tr>
        <td><b>1</b></td>
        <td><b>P4</b></td>
        <td>FBS Power 4 (SEC, B1G, B12, ACC, ND)</td>
        <td>0</td>
    </tr>
    <tr>
        <td><b>2</b></td>
        <td><b>G5</b></td>
        <td>FBS Group of 5</td>
        <td>-15</td>
    </tr>
    <tr>
        <td><b>3</b></td>
        <td><b>FCS Pwr</b></td>
        <td>MVFC, Big Sky, CAA, etc.</td>
        <td>-45</td>
    </tr>
    <tr>
        <td><b>4</b></td>
        <td><b>FCS Std</b></td>
        <td>MEAC, Pioneer, Patriot, etc.</td>
        <td>-65</td>
    </tr>
    <tr>
        <td><b>5</b></td>
        <td><b>D2 Pwr</b></td>
        <td>GLIAC, Gulf South, etc.</td>
        <td>-85</td>
    </tr>
    <tr>
        <td><b>6-8</b></td>
        <td><b>Lower</b></td>
        <td>D2 Std, D3 Pwr, D3 Std</td>
        <td>-105 to -145</td>
    </tr>
</table>

### 2. Recursive Scoring
* **Pass 0:** Teams are graded based on raw Win % and Tier Weight.

* **Pass 1:** Games are re-graded based on the Pass 0 SOR of the opponent.

* **Pass 2:** Refinement. Beating a 10-2 team that played a weak schedule is worth less than beating a 10-2 team that played a gauntlet.

### 3. Game Modifiers
* **Upset Bonus:** Lower Tier beating Higher Tier (e.g., FCS over FBS) grants a massive multiplier (up to 2.0x).

* **Bully Penalty:** Higher Tier beating Lower Tier (e.g., FBS over D3) yields diminishing returns (down to 0.1x).

* **Bad Loss Penalty:** Losing to a team in a lower tier incurs a steep penalty.

* **Margin of Victory:** Capped at 28 points to prevent running up the score.


## Troubleshooting

### "Rank" KeyError or Weird Tier Data
If teams like "Springfield" (D3) show up as Tier 2, or you get KeyErrors:

1. Run the repair script to fix cached metadata:

```Bash
python3 scripts/repair_teams.py
```
2. Re-run your query.

### Missing Data or "No Path Found"
To reset everything and fetch fresh data:
```Bash
rm data/*.json
python3 scripts/build_games_db.py
python3 scripts/repair_teams.py
python3 scripts/build_stats_db.py
```