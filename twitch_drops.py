import json
import requests
import uuid
from datetime import datetime, timedelta, timezone

def fetch_drops():
    print("--- Initializing Stealth GraphQL Discovery ---")
    
    url = "https://gql.twitch.tv/gql"
    
    # Twitch's internal API is very picky about headers. 
    # These mimic a logged-out user on a fresh Chrome browser.
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "X-Device-Id": uuid.uuid4().hex,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://www.twitch.tv",
        "Referer": "https://www.twitch.tv/drops/campaigns"
    }
    
    # This SHA256 Hash is the internal Twitch ID for the "All Campaigns" list.
    # It provides the most detailed data including reward images.
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

        data = res.json()
        # Navigate the complex nested JSON
        all_campaigns = data[0].get("data", {}).get("dropCampaigns", [])
        
        print(f"Scanned {len(all_campaigns)} global campaigns.")

        active_predecessor_drops = []
        now = datetime.now(timezone.utc)

        for camp in all_campaigns:
            game = camp.get("game", {})
            # Predecessor Game ID is 515056
            if game.get("id") == "515056" or "Predecessor" in game.get("name", ""):
                
                # Check if campaign is active based on time
                try:
                    start = datetime.strptime(camp['startAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    end = datetime.strptime(camp['endAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    
                    if start <= now <= end:
                        print(f"!!! ACTIVE DROPS DETECTED: {camp['name']}")
                        
                        rewards = []
                        # Dig into time-based rewards
                        for drop in camp.get("timeBasedDrops", []):
                            # Usually benefits are in an array
                            for edge in drop.get("benefitEdges", []):
                                benefit = edge.get("benefit", {})
                                rewards.append({
                                    "name": benefit.get("name") or drop.get("name"),
                                    "image": benefit.get("imageAssetURL"),
                                    "minutes": drop.get("requiredMinutesWatched")
                                })
                        
                        active_predecessor_drops.append({
                            "campaign_name": camp['name'],
                            "rewards": rewards
                        })
                except Exception as e:
                    print(f"Date parsing error: {e}")

        # Save results (Time adjusted for CEST/Germany)
        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_predecessor_drops) > 0,
            "campaigns": active_predecessor_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
            
        print(f"Scrape successful. Active: {output['active']}")

    except Exception as e:
        print(f"Critical Error: {e}")
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns": [], "last_updated": "Error"}, f, indent=4)

if __name__ == "__main__":
    fetch_drops()
