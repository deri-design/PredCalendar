import json
import requests
from datetime import datetime

def fetch_drops():
    print("--- Connecting to Twitch Internal GraphQL ---")
    
    url = "https://gql.twitch.tv/gql"
    # 'kimne78kx3ncx6brgo4mv6wki5h1ko' is Twitch's universal public Client-ID
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "Content-Type": "application/json"
    }
    
    # We query the Game object specifically for Predecessor's Drop Campaigns
    payload = {
        "query": """
        query {
          game(name: "Predecessor") {
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
        
        active_drops =[]
        game_data = data.get("data", {}).get("game")
        
        if game_data and game_data.get("dropCampaigns"):
            for camp in game_data["dropCampaigns"]:
                if camp.get("status") == "ACTIVE":
                    rewards = []
                    for drop in camp.get("timeBasedDrops",[]):
                        for edge in drop.get("benefitEdges",[]):
                            benefit = edge.get("benefit", {})
                            rewards.append({
                                "name": benefit.get("name"),
                                "image": benefit.get("imageAssetURL"),
                                "minutes": drop.get("requiredMinutesWatched")
                            })
                            
                    active_drops.append({
                        "campaign_name": camp.get("name"),
                        "start": camp.get("startAt"),
                        "end": camp.get("endAt"),
                        "rewards": rewards
                    })
        
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active": len(active_drops) > 0,
            "campaigns": active_drops
        }
        
        # Saves to a COMPLETELY SEPARATE file
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
            
        print(f"Success! Twitch Drops Active: {output['active']}")
        
    except Exception as e:
        print(f"Error fetching Twitch Drops: {e}")
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns":[]}, f)

if __name__ == "__main__":
    fetch_drops()
