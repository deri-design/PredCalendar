import json
import requests
import uuid
import re
from datetime import datetime, timedelta, timezone

def fetch_drops():
    print("--- Connecting to Twitch via Session Spoof (Unblockable Mode) ---")
    
    # Using a requests session to handle cookies automatically
    session = requests.Session()
    
    # Standard headers for a high-end Chrome browser
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "X-Device-Id": uuid.uuid4().hex,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": "https://www.twitch.tv",
        "Referer": "https://www.twitch.tv/drops/campaigns"
    }

    # Step 1: Visit the public campaigns page to establish a "Human" session
    try:
        session.get("https://www.twitch.tv/drops/campaigns", headers=headers, timeout=10)
        print("Session established with Twitch.")
    except:
        print("Initial session connection failed, proceeding anyway...")

    # Step 2: Use the 'ViewerDropsDashboard' operation
    # This is the public API call used by the 'All Campaigns' tab
    payload = [{
        "operationName": "ViewerDropsDashboard",
        "variables": {"inventory": False},
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "e1edcc7790435349e5898d2b0e77d943477e685f060c410427c328905357f89c"
            }
        }
    }]

    try:
        url = "https://gql.twitch.tv/gql"
        res = session.post(url, headers=headers, json=payload, timeout=15)
        
        if res.status_code != 200:
            print(f"Twitch rejected GraphQL call: {res.status_code}")
            return

        data = res.json()
        # Extract the list of campaigns
        campaigns = data[0].get("data", {}).get("dropCampaigns", [])
        
        if not campaigns:
            print("Twitch returned 0 active campaigns globally. Detection likely.")
            return

        print(f"Successfully scanned {len(campaigns)} global campaigns.")
        
        active_predecessor_drops = []
        now = datetime.now(timezone.utc)

        for camp in campaigns:
            game_name = camp.get("game", {}).get("name", "")
            camp_name = camp.get("name", "")
            
            # Match Predecessor in either game name or campaign title
            if "Predecessor" in game_name or "Predecessor" in camp_name:
                print(f"!!! MATCH FOUND: {camp_name} (Status: {camp.get('status')})")
                
                # Check status and manual time window
                status = camp.get('status', '').upper()
                is_active = (status == "ACTIVE")
                
                if not is_active:
                    try:
                        start = datetime.strptime(camp['startAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        end = datetime.strptime(camp['endAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        if start <= now <= end:
                            is_active = True
                    except: pass

                if is_active:
                    rewards = []
                    # Extract rewards and watch time
                    for drop in camp.get("timeBasedDrops", []):
                        for edge in drop.get("benefitEdges", []):
                            benefit = edge.get("benefit", {})
                            rewards.append({
                                "name": benefit.get("name") or drop.get("name"),
                                "image": benefit.get("imageAssetURL") or "https://static-cdn.jtvnw.net/drops/assets/predecessor_default.png",
                                "minutes": drop.get("requiredMinutesWatched")
                            })
                    
                    active_predecessor_drops.append({
                        "campaign_name": camp_name,
                        "rewards": rewards
                    })

        # Calculate CEST (German Time)
        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_predecessor_drops) > 0,
            "campaigns": active_predecessor_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Final Result: {'Drops Detected!' if output['active'] else 'No Predecessor Drops found.'}")

    except Exception as e:
        print(f"Process Error: {e}")
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns": [], "last_updated": "Error"}, f, indent=4)

if __name__ == "__main__":
    fetch_drops()
