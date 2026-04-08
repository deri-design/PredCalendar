import json
import requests
import uuid
import re
from datetime import datetime, timedelta, timezone

def fetch_drops():
    print("--- Initializing Stealth GraphQL Sync (DropHunter Method) ---")
    
    url = "https://gql.twitch.tv/gql"
    
    # These headers are the secret. They mimic a real, logged-out Chrome user.
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", # Official Twitch Web Client ID
        "X-Device-Id": uuid.uuid4().hex, # Unique hardware fingerprint
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Origin": "https://www.twitch.tv",
        "Referer": "https://www.twitch.tv/drops/campaigns"
    }
    
    # This specific SHA256 Hash tells Twitch: "Give me the public Viewer Dashboard data"
    # This is exactly what the public /drops/campaigns page asks for.
    payload = [{
        "operationName": "ViewerDropsDashboard",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "e1edcc7790435349e5898d2b0e77d943477e685f060c410427c328905357f89c"
            }
        },
        "variables": {
            "inventory": False
        }
    }]

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        
        if res.status_code != 200:
            print(f"Twitch rejected connection: {res.status_code}")
            return

        response_json = res.json()
        # Twitch returns a list because we sent a batched request
        data = response_json[0] if isinstance(response_json, list) else response_json
        
        all_campaigns = data.get("data", {}).get("dropCampaigns", [])
        print(f"Scanned {len(all_campaigns)} global campaigns.")

        active_predecessor_drops = []
        now = datetime.now(timezone.utc)

        for camp in all_campaigns:
            game = camp.get("game", {})
            # Predecessor Game ID is 515056
            if game.get("id") == "515056" or "Predecessor" in game.get("name", ""):
                
                # Check status and time window
                status = camp.get('status', '').upper()
                is_active = (status == "ACTIVE")
                
                # Fallback check: Twitch API status can lag, so check the clock too
                if not is_active:
                    try:
                        start = datetime.strptime(camp['startAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        end = datetime.strptime(camp['endAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        if start <= now <= end:
                            is_active = True
                    except: pass

                if is_active:
                    print(f"!!! MATCH FOUND: {camp['name']}")
                    rewards = []
                    for drop in camp.get("timeBasedDrops", []):
                        for edge in drop.get("benefitEdges", []):
                            benefit = edge.get("benefit", {})
                            rewards.append({
                                "name": benefit.get("name") or drop.get("name"),
                                "image": benefit.get("imageAssetURL") or "https://static-cdn.jtvnw.net/drops/assets/predecessor_default.png",
                                "minutes": drop.get("requiredMinutesWatched")
                            })
                    
                    active_predecessor_drops.append({
                        "campaign_name": camp['name'],
                        "rewards": rewards
                    })

        # Save to file (CEST adjustment included)
        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_predecessor_drops) > 0,
            "campaigns": active_predecessor_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
            
        print(f"Sync complete. Active Predecessor Drops: {output['active']}")

    except Exception as e:
        print(f"Scrape Error: {e}")
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns": [], "last_updated": "Error"}, f, indent=4)

if __name__ == "__main__":
    fetch_drops()
