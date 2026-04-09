import json
import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

def fetch_drops():
    print("--- Synchronisiere Twitch Drops (Präzisions-Modus) ---")
    
    url = "https://twitchdrops.app/game/predecessor"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    }

    active_campaigns = []

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return

        html = response.text
        # Ignoriere alles nach "PAST DROPS"
        active_html = re.split(r'PAST DROPS', html, flags=re.IGNORECASE)[0]
        
        # Suche nach dem JSON-Datenblock
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        
        if next_data_match:
            data = json.loads(next_data_match.group(1))
            
            # Rekursive Suche nach Predecessor-Kampagnen im JSON
            def find_campaigns(obj):
                found = []
                if isinstance(obj, dict):
                    if ('items' in obj or 'drops' in obj) and ('endAt' in obj or 'ends_at' in obj):
                        if "Predecessor" in json.dumps(obj):
                            found.append(obj)
                    for v in obj.values():
                        res = find_campaigns(v)
                        if res: found.extend(res)
                elif isinstance(obj, list):
                    for i in obj:
                        res = find_campaigns(i)
                        if res: found.extend(res)
                return found

            candidates = find_campaigns(data)
            now = datetime.now(timezone.utc)

            for camp in candidates:
                end_str = camp.get('endAt') or camp.get('ends_at')
                start_str = camp.get('startAt') or camp.get('starts_at')
                
                if not end_str: continue
                
                try:
                    end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    if end_dt > now:
                        print(f"Aktive Kampagne gefunden: {camp.get('name', 'Predecessor Drops')}")
                        rewards = []
                        items = camp.get('items') or camp.get('drops') or []
                        for it in items:
                            img = it.get('image') or it.get('image_url') or ""
                            if img.startswith('/'): img = "https://twitchdrops.app" + img
                            rewards.append({
                                "name": it.get('name', 'Belohnung'),
                                "image": img,
                                "minutes": int(it.get('requiredMinutes') or it.get('minutes') or 60)
                            })
                        
                        if rewards:
                            active_campaigns.append({
                                "campaign_name": camp.get('name') or "1.13 Premium Drops",
                                "start": start_str,
                                "end": end_str,
                                "rewards": rewards
                            })
                except: continue

        # Fallback: HTML Parsing falls JSON scheitert
        if not active_campaigns:
            soup = BeautifulSoup(active_html, 'parser')
            # Hier würden wir nach den Karten suchen (ähnlich wie vorher)
            pass

    except Exception as e:
        print(f"Fehler: {e}")

    german_time = datetime.now(timezone.utc) + timedelta(hours=2)
    output = {
        "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
        "active": len(active_campaigns) > 0,
        "campaigns": active_campaigns
    }
    
    with open('drops.json', 'w') as f:
        json.dump(output, f, indent=4)

if __name__ == "__main__":
    fetch_drops()
