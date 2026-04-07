import json
import requests
from datetime import datetime, timedelta, timezone

def fetch_drops():
    print("--- DIAGNOSTIC: Fetching Global Twitch Drops ---")
    
    url = "https://gql.twitch.tv/gql"
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", # Universal Twitch Web ID
        "Content-Type": "application/json"
    }
    
    # We use the full query text instead of a 'Hash' to make it harder to break
    query = """
    query {
        dropCampaigns(itemTypes: [ENUM]) {
            name
            status
            startAt
            endAt
            game {
                id
                name
            }
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
    """
    
    payload = {"query": query}

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        data = res.json()
        
        all_campaigns = data.get("data", {}).get("dropCampaigns", [])
        print(f"Total campaigns found on Twitch: {len(all_campaigns)}")
        
        active_predecessor_drops = []
        found_games = []

        for camp in all_campaigns:
            game_name = camp.get("game", {}).get("name", "Unknown")
            found_games.append(game_name)
            
            # Filter for Predecessor
            if "Predecessor" in game_name:
                print(f"!!! PREDECESSOR FOUND: {camp['name']} (Status: {camp['status']})")
                
                # Check time window manually to be safe
                now = datetime.now(timezone.utc)
                is_in_window = False
                try:
                    start = datetime.strptime(camp['startAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    end = datetime.strptime(camp['endAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    is_in_window = start <= now <= end
                except: pass

                if camp['status'] == "ACTIVE" or is_in_window:
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

        # LOG THE FIRST 10 GAMES FOUND FOR DEBUGGING
        print(f"Sample of games found with drops: {', '.join(list(set(found_games))[:10])}")

        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_predecessor_drops) > 0,
            "campaigns": active_predecessor_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"File Saved. Active: {output['active']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_drops()
