import json
import requests
from datetime import datetime, timezone

def fetch_drops():
    print("--- Connecting to Twitch Internal GraphQL ---")
    
    url = "https://gql.twitch.tv/gql"
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "Content-Type": "application/json"
    }
    
    # We use Game ID '515056' (Predecessor) to bypass name-matching errors
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
        
        active_drops =[]
        game_data = data.get("data", {}).get("game")
        
        if not game_data:
            print("Error: Twitch returned empty game data.")
            print(f"Raw Response: {data}")
        elif not game_data.get("dropCampaigns"):
            print("Twitch returned game, but no drop campaigns found.")
        else:
            now = datetime.now(timezone.utc)
            
            for camp in game_data["dropCampaigns"]:
                c_name = camp.get('name', 'Unknown Campaign')
                c_status = camp.get('status', '')
                c_start = camp.get('startAt', '')
                c_end = camp.get('endAt', '')
                
                print(f"Found Campaign: {c_name} | Status: {c_status} | Starts: {c_start}")
                
                is_active = False
                
                # 1. Check if Twitch officially marked it active
                if c_status.upper() == "ACTIVE":
                    is_active = True
                
                # 2. Hard check: If status is lagging, check the actual timestamps
                elif c_start and c_end:
                    try:
                        start_dt = datetime.strptime(c_start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        end_dt = datetime.strptime(c_end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        if start_dt <= now <= end_dt:
                            print(f"-> Forcing Active: Current time is within campaign window.")
                            is_active = True
                    except Exception as e:
                        print(f"-> Time parse error: {e}")

                if is_active:
                    rewards =[]
                    for drop in camp.get("timeBasedDrops", []):
                        for edge in drop.get("benefitEdges",[]):
                            benefit = edge.get("benefit", {})
                            rewards.append({
                                "name": benefit.get("name") or drop.get("name", "Reward"),
                                "image": benefit.get("imageAssetURL") or "https://static-cdn.jtvnw.net/drops/assets/predecessor_default.png",
                                "minutes": drop.get("requiredMinutesWatched")
                            })
                    
                    active_drops.append({
                        "campaign_name": c_name,
                        "start": c_start,
                        "end": c_end,
                        "rewards": rewards
                    })
        
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active": len(active_drops) > 0,
            "campaigns": active_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
            
        print(f"Success! Twitch Drops Active: {output['active']}")
        
    except Exception as e:
        print(f"Critical error fetching Twitch Drops: {e}")
        # Make sure the file exists so the workflow doesn't crash
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns":
