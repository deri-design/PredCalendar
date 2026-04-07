import json
import requests
import uuid
from datetime import datetime, timedelta, timezone

def fetch_drops():
    print("--- Connecting to Twitch GraphQL (Browser Mimic Mode) ---")
    
    url = "https://gql.twitch.tv/gql"
    
    # We generate a random Device ID and use real browser headers to bypass bot detection
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "X-Device-Id": uuid.uuid4().hex,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "*/*"
    }
    
    # This is the exact data structure Twitch uses for the public drops page
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
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        response_data = res.json()
        
        # Twitch sometimes returns a list, sometimes a single object
        data = response_data[0] if isinstance(response_data, list) else response_data
        all_campaigns = data.get("data", {}).get("dropCampaigns", [])
        
        # --- FALLBACK: If Persisted Query fails, try Raw Query ---
        if not all_campaigns:
            print("Method 1 returned 0. Trying Method 2 (Raw Query)...")
            raw_payload = {
                "query": """
                query {
                    dropCampaigns {
                        name
                        status
                        startAt
                        endAt
                        game { id name }
                        timeBasedDrops {
                            name
                            requiredMinutesWatched
                            benefitEdges { benefit { name imageAssetURL } }
                        }
                    }
                }
                """
            }
            res = requests.post(url, headers=headers, json=raw_payload, timeout=15)
            all_campaigns = res.json().get("data", {}).get("dropCampaigns", [])

        print(f"Total Twitch Campaigns Scanned: {len(all_campaigns)}")
        
        active_predecessor_drops = []
        now = datetime.now(timezone.utc)

        for camp in all_campaigns:
            game = camp.get("game", {})
            # Match by Predecessor Name or Game ID (515056)
            if game and ("Predecessor" in game.get("name", "") or game.get("id") == "515056"):
                
                # Check time window (Twitch 'status' can be slow to update)
                is_active = camp.get('status') == "ACTIVE"
                if not is_active:
                    try:
                        start = datetime.strptime(camp['startAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        end = datetime.strptime(camp['endAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        is_active = start <= now <= end
                    except: pass

                if is_active:
                    print(f"Found Live Drops: {camp['name']}")
                    rewards = []
                    for drop in camp.get("timeBasedDrops", []):
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

        # Final Timestamp in German Time
        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_predecessor_drops) > 0,
            "campaigns": active_predecessor_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Scrape Finished. Predecessor Drops Active: {output['active']}")

    except Exception as e:
        print(f"Scrape Failed: {e}")
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns": [], "last_updated": "Error"}, f, indent=4)

if __name__ == "__main__":
    fetch_drops()
