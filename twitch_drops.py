import json
import requests
import re
from datetime import datetime, timedelta, timezone

def fetch_drops():
    print("--- Connecting to Twitch Drops (Public Overlay Mode) ---")
    
    # We use the public campaigns page which contains the data in a script tag
    url = "https://www.twitch.tv/drops/campaigns"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
        
        print(f"Page fetched. Status: {response.status_code}")

        # Twitch hides the data inside a JSON block called 'dropCampaigns' in the HTML
        # We use Regex to find the data for Predecessor (Game ID: 515056)
        
        active_campaigns = []
        
        # 1. Look for the JSON data in the script tags
        json_blobs = re.findall(r'<script type="application/json">.*?"dropCampaigns":\[(.*?)\].*?</script>', html)
        
        if not json_blobs:
            # Fallback to a broader search if the specific tag changed
            json_blobs = re.findall(r'"dropCampaigns":\[(.*?)(?:\],"|\}\])', html)

        if json_blobs:
            # Reconstruct the list string into actual objects
            raw_data = "[" + json_blobs[0] + "]"
            try:
                # We do some cleanup to handle Twitch's massive nested JSON
                # We search for Predecessor's specific ID within the raw text first to save time
                if "515056" in raw_data or "Predecessor" in raw_data:
                    data = json.loads(raw_data)
                    
                    now = datetime.now(timezone.utc)

                    for camp in data:
                        game = camp.get("game", {})
                        if game.get("id") == "515056" or "Predecessor" in game.get("name", ""):
                            print(f"Found Campaign: {camp.get('name')}")
                            
                            # Standardize time check
                            try:
                                start = datetime.strptime(camp['startAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                                end = datetime.strptime(camp['endAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                                
                                if start <= now <= end:
                                    rewards = []
                                    for drop in camp.get("timeBasedDrops", []):
                                        for edge in drop.get("benefitEdges", []):
                                            benefit = edge.get("benefit", {})
                                            rewards.append({
                                                "name": benefit.get("name") or drop.get("name"),
                                                "image": benefit.get("imageAssetURL"),
                                                "minutes": drop.get("requiredMinutesWatched")
                                            })
                                    
                                    active_campaigns.append({
                                        "campaign_name": camp.get("name"),
                                        "rewards": rewards
                                    })
                            except: continue
            except Exception as e:
                print(f"JSON Parse Error: {e}")
        else:
            print("Could not find the 'dropCampaigns' data block in HTML.")

        # Final Timestamp in German Time (UTC+2)
        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_campaigns) > 0,
            "campaigns": active_campaigns
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
            
        print(f"Scrape Complete. Active: {output['active']}")

    except Exception as e:
        print(f"Critical Error: {e}")
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns": [], "last_updated": "Error"}, f, indent=4)

if __name__ == "__main__":
    fetch_drops()
