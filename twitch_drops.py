import json
import requests
from datetime import datetime, timezone

def fetch_drops():
    print("--- Connecting to Twitch Internal GraphQL ---")
    
    url = "https://gql.twitch.tv/gql"
    # Twitch's universal public Client-ID
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "Content-Type": "application/json"
    }
    
    # Querying Predecessor (ID: 515056) specifically for active drops
    payload = {
        "query": """
        query {
          game(id: "515056") {
            id
            name
            dropCampaigns {
              id
              name
              status
              startAt
              endAt
              timeBasedDrops {
                name
                requiredMinutesWatched
                benefitEdges {
                  benefit {
                    name
                    imageAssetURL
                  }
                }
              }
            }
          }
        }
        """
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        data = res.json()
        
        active_drops = []
        game_data = data.get("data", {}).get("game")
        
        if game_data and game_data.get("dropCampaigns"):
            now = datetime.now(timezone.utc)
            
            for camp in game_data["dropCampaigns"]:
                c_status = camp.get('status', '').upper()
                c_start = camp.get('startAt', '')
                c_end = camp.get('endAt', '')
                
                is_actually_active = False
                if c_status == "ACTIVE":
                    is_actually_active = True
                elif c_start and c_end:
                    # Fallback check for time window if status is lagging
                    st = datetime.strptime(c_start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    en = datetime.strptime(c_end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    if st <= now <= en:
                        is_actually_active = True

                if is_actually_active:
                    rewards = []
                    for drop in camp.get("timeBasedDrops", []):
                        for edge in drop.get("benefitEdges", []):
                            benefit = edge.get("benefit", {})
                            rewards.append({
                                "name": benefit.get("name") or drop.get("name"),
                                "image": benefit.get("imageAssetURL"),
                                "minutes": drop.get("requiredMinutesWatched")
                            })
                    
                    active_drops.append({
                        "campaign_name": camp.get("name"),
                        "rewards": rewards
                    })
        
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active": len(active_drops) > 0,
            "campaigns": active_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Success! Active campaigns: {len(active_drops)}")
        
    except Exception as e:
        print(f"Error: {e}")
        # Safeguard: Write empty file if it fails
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns": []}, f, indent=4)

if __name__ == "__main__":
    fetch_drops()
