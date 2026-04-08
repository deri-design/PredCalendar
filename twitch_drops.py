import json
import requests
import os
from datetime import datetime, timedelta, timezone

# Config from GitHub Secrets
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

def get_access_token():
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    res = requests.post(url, params=params)
    return res.json().get("access_token")

def fetch_drops():
    print("--- Connecting to Official Twitch Helix API ---")
    
    token = get_access_token()
    if not token:
        print("Failed to get Twitch Access Token. Check your Secrets.")
        return

    headers = {
        "Client-Id": CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }

    # Endpoint for all active drop campaigns
    url = "https://api.twitch.tv/helix/drops/campaigns"
    
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        
        all_campaigns = data.get("data", [])
        print(f"Total campaigns on Twitch: {len(all_campaigns)}")
        
        active_predecessor_drops = []
        
        for camp in all_campaigns:
            # Predecessor Game ID is 515056
            if camp.get("game", {}).get("id") == "515056":
                # Helix only returns active/upcoming by default
                status = camp.get("status")
                print(f"Found Predecessor Campaign: {camp.get('name')} [{status}]")
                
                if status == "ACTIVE":
                    rewards = []
                    # Helix has a slightly different structure for rewards
                    # We grab the benefit info from the campaign
                    for drop in camp.get("button_entitlements", []):
                        # Note: Helix provides less visual detail than GQL, 
                        # but we can map the names to icons manually if needed.
                        rewards.append({
                            "name": drop.get("name", "Drop Reward"),
                            "image": "https://static-cdn.jtvnw.net/drops/assets/predecessor_default.png",
                            "minutes": 60 # Defaulting to 60 as Helix doesn't show minutes easily
                        })
                    
                    active_predecessor_drops.append({
                        "campaign_name": camp.get("name"),
                        "rewards": rewards
                    })

        # German Time Timestamp
        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_predecessor_drops) > 0,
            "campaigns": active_predecessor_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Success! Active: {output['active']}")

    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    fetch_drops()
