import sys
import os
import json
import cfbd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

OUTPUT_FILE = config.TEAMS_CACHE_FILE
# Use the current/most recent season to ensure we get active affiliations
TARGET_YEAR = 2024 

def main():
    print(f"BUILDING TEAMS CACHE (Year: {TARGET_YEAR})...")
    
    # 1. Setup API (Manual Header Injection)
    configuration = cfbd.Configuration()
    api_client = cfbd.ApiClient(configuration)
    api_client.default_headers['Authorization'] = f"Bearer {config.API_KEY}"
    api_instance = cfbd.TeamsApi(api_client)

    try:
        # 2. Fetch Teams for Specific Year
        # requesting a year forces the API to populate 'conference' and 'classification'
        print(f"   Downloading team data for {TARGET_YEAR}...")
        teams = api_instance.get_teams(year=TARGET_YEAR)
        
        # 3. Clean & Serialize
        teams_data = []
        for t in teams:
            # Classification Fallback:
            # If API still returns None, we default to 'unknown' to prevent math errors later
            cls = t.classification if t.classification else 'unknown'
            conf = t.conference if t.conference else 'unknown'

            teams_data.append({
                'id': t.id,
                'school': t.school,
                'mascot': t.mascot,
                'abbreviation': t.abbreviation,
                'conference': conf,
                'division': t.division,
                'color': t.color,
                'logos': t.logos,
                'classification': cls,
                'location': {
                    'name': t.location.name if t.location else None,
                    'city': t.location.city if t.location else None,
                    'state': t.location.state if t.location else None,
                }
            })

        # 4. Save
        print(f"   Saving {len(teams_data)} teams to {OUTPUT_FILE}...")
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(teams_data, f, indent=2)
            
        print("Done! Cache refreshed.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()