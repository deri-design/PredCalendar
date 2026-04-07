import json
import requests
import re
import uuid
from datetime import datetime, timedelta, timezone

def fetch_drops():
    print("--- Connecting to Twitch (Survivor Extraction Mode) ---")
    
    # Predecessor Game ID on Twitch
    GAME_ID = "515056"
    
    url = "https://www.twitch.tv/drops/campaigns"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "X-Device-Id": uuid.uuid4().hex,
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }

    active_campaigns = []

    try:
        # Step 1: Try a clean GET request to the public page
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
        
        # Step 2: Use a "Greedy" Regex to find the JSON data block for Predecessor
        # We look for the game ID and capture the surrounding campaign data
        print("Scanning HTML for Predecessor drop signatures...")
        
        # Find the specific block of JSON that contains Predecessor info
        pattern = r'\{"id":"' + GAME_ID + r'".*?\}'
        matches = re.findall(pattern, html)
        
        if matches:
            print(f"Found {len(matches)} potential data matches in HTML.")
            for match in matches:
                try:
                    # Try to reconstruct valid JSON from the snippet
                    # This often contains the Campaign Name and Status
                    if '"status":"ACTIVE"' in match or '"status":"UPCOMING"' in match:
                        name_match = re.search(r'"name":"([^"]+)"', match)
                        name = name_match.group(1) if name_match else "Predecessor Drops"
                        
                        # Only add if it's not a duplicate
                        if not any(c['campaign_name'] == name for c in active_campaigns):
                            active_campaigns.append({
                                "campaign_name": name,
                                "rewards": [
                                    {"name": "Loot Cores / Skins", "image": "https://static-cdn.jtvnw.net/drops/assets/predecessor_default.png", "minutes": "60-120"}
                                ]
                            })
                            print(f"Captured: {name}")
                except:
                    continue

        # Step 3: API Fallback (Direct GQL call with simplified structure)
        if not active_campaigns:
            print("HTML extraction failed. Attempting targeted API punch-through...")
            api_url = "https://gql.twitch.tv/gql"
            gql_query = """
            query {
              game(id: "515056") {
                dropCampaigns {
                  name
                  status
                  timeBasedDrops { name requiredMinutesWatched }
                }
              }
            }
            """
            res = requests.post(api_url, headers=headers, json={"query": gql_query}, timeout=10)
            data = res.json().get("data", {}).get("game", {})
            if data and data.get("dropCampaigns"):
                for camp in data["dropCampaigns"]:
                    if camp["status"] == "ACTIVE":
                        active_campaigns.append({
                            "campaign_name": camp["name"],
                            "rewards": [{"name": "Twitch Rewards", "image": "", "minutes": "60"}]
                        })

    except Exception as e:
        print(f"Extraction error: {e}")

    # Step 4: Final Timestamp and Output
    # Generate CEST (German Time)
    german_time = datetime.now(timezone.utc) + timedelta(hours=2)
    
    output = {
        "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
        "active": len(active_campaigns) > 0,
        "campaigns": active_campaigns
    }

    with open('drops.json', 'w') as f:
        json.dump(output, f, indent=4)
        
    print(f"Process complete. Active: {output['active']}")

if __name__ == "__main__":
    fetch_drops()
