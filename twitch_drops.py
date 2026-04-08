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
        print("Error: Could not get access token. Check Client ID/Secret.")
        return

    headers = {
        "Client-Id": CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }

    # Fetch all active drop campaigns globally
    url = "https://api.twitch.tv/helix/drops/campaigns"
    
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        
        all_campaigns = data.get("data", [])
        active_predecessor_drops = []
        
        for camp in all_campaigns:
            # Predecessor Game ID: 515056
            if str(camp.get("game", {}).get("id")) == "515056":
                status = camp.get("status")
                print(f"Found Predecessor Campaign: {camp.get('name')} [{status}]")
                
                # We only show it on the site if it is currently ACTIVE
                if status == "ACTIVE":
                    rewards = []
                    # Helix rewards structure is simple, we map them to our UI
                    # We look for the 'allow' list which usually contains reward names
                    for entitlement in camp.get("button_entitlements", []):
                        rewards.append({
                            "name": entitlement.get("name", "Drop Reward"),
                            "image": "https://static-cdn.jtvnw.net/drops/assets/predecessor_default.png",
                            "minutes": 60 # Helix doesn't provide easy minute data, defaulting to 60
                        })
                    
                    active_predecessor_drops.append({
                        "campaign_name": camp.get("name"),
                        "rewards": rewards
                    })

        # German Time (CEST) for the footer
        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_predecessor_drops) > 0,
            "campaigns": active_predecessor_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Process Complete. Active Drops: {output['active']}")

    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    fetch_drops()
