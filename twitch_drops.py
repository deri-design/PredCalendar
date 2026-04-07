import json
import requests
import uuid
from datetime import datetime, timedelta, timezone

def process_camp(camp):
    """Formats raw Twitch data into our clean rewards structure."""
    rewards = []
    for drop in camp.get("timeBasedDrops", []):
        for edge in drop.get("benefitEdges", []):
            benefit = edge.get("benefit", {})
            rewards.append({
                "name": benefit.get("name") or drop.get("name", "Reward"),
                "image": benefit.get("imageAssetURL") or "https://static-cdn.jtvnw.net/drops/assets/predecessor_default.png",
                "minutes": drop.get("requiredMinutesWatched")
            })
    return {
        "campaign_name": camp.get("name", "Unknown Campaign"),
        "rewards": rewards
    }

def fetch_drops():
    print("--- Connecting to Twitch GraphQL (Discovery Mode) ---")
    
    url = "https://gql.twitch.tv/gql"
    # kimne78kx3ncx6brgo4mv6wki5h1ko is Twitch's public front-end ID
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "X-Device-Id": uuid.uuid4().hex,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://www.twitch.tv"
    }

    # We fetch ALL active campaigns to bypass game-specific shielding
    query = """
    query {
      dropCampaigns {
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

    active_campaigns = []
    try:
        response = requests.post(url, headers=headers, json={"query": query}, timeout=15)
        
        if response.status_code != 200:
            print(f"Twitch rejected request: {response.status_code}")
            return

        data = response.json()
        all_camps = data.get("data", {}).get("dropCampaigns", [])
        
        # Log for debugging
        print(f"Total campaigns found on Twitch: {len(all_camps)}")

        now = datetime.now(timezone.utc)
        
        for camp in all_camps:
            game = camp.get("game")
            if not game: continue
            
            # Match Predecessor by ID (515056) or Name
            if game.get("id") == "515056" or "Predecessor" in game.get("name", ""):
                print(f"!!! MATCH FOUND: {camp['name']} (Twitch Status: {camp['status']})")
                
                # Double-check time window because Twitch status updates can lag
                is_live = (camp.get('status') == "ACTIVE")
                if not is_live:
                    try:
                        start = datetime.strptime(camp['startAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        end = datetime.strptime(camp['endAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        if start <= now <= end:
                            print("-> Manually verifying as active based on clock.")
                            is_live = True
                    except: pass
                
                if is_live:
                    active_campaigns.append(process_camp(camp))

    except Exception as e:
        print(f"Scrape error: {e}")

    # Generate CEST Timestamp (UTC+2) for your clock
    german_time = datetime.now(timezone.utc) + timedelta(hours=2)
    output = {
        "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
        "active": len(active_campaigns) > 0,
        "campaigns": active_campaigns
    }

    with open('drops.json', 'w') as f:
        json.dump(output, f, indent=4)
    
    print(f"Process Complete. Active: {output['active']}")

if __name__ == "__main__":
    fetch_drops()
