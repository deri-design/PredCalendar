import json
import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

def fetch_drops():
    print("--- Start Unstoppable Scrape: TwitchDrops.app (Predecessor) ---")
    
    url = "https://twitchdrops.app/game/predecessor"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    }

    active_campaigns = []

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Fehler: Seite konnte nicht geladen werden (Status {response.status_code})")
            return

        # Wir trennen die Seite bei "PAST DROPS", um nur aktuelle Belohnungen zu sehen
        parts = re.split(r'PAST DROPS', response.text, flags=re.IGNORECASE)
        active_html = parts[0]
        
        # --- LOGIK: JSON TIEFENSCAN ---
        # Suche nach dem __NEXT_DATA__ Block
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
        
        if next_data_match:
            print("JSON Datenblock gefunden. Extrahiere Kampagnen...")
            data = json.loads(next_data_match.group(1))
            
            # Wir suchen rekursiv nach Listen, die 'Predecessor' enthalten
            def find_predecessor_campaigns(obj):
                found = []
                if isinstance(obj, dict):
                    # Wenn dieses Objekt eine Kampagne mit Belohnungen (items) ist
                    if obj.get('gameName') == 'Predecessor' or obj.get('game_id') == 515056:
                        if isinstance(obj.get('items'), list) or isinstance(obj.get('drops'), list):
                            found.append(obj)
                    for v in obj.values():
                        res = find_predecessor_campaigns(v)
                        if res: found.extend(res)
                elif isinstance(obj, list):
                    for i in obj:
                        res = find_predecessor_campaigns(i)
                        if res: found.extend(res)
                return found

            all_matches = find_predecessor_campaigns(data)
            
            for camp in all_matches:
                # Wir nehmen nur Kampagnen, die laut Status ACTIVE sind
                if str(camp.get('status', '')).upper() == 'ACTIVE':
                    print(f"Aktive Kampagne gefunden: {camp.get('title') or camp.get('name')}")
                    rewards = []
                    items = camp.get('items') or camp.get('drops') or []
                    for it in items:
                        img = it.get('image') or it.get('image_url') or ""
                        if img and img.startswith('/'): img = "https://twitchdrops.app" + img
                        
                        rewards.append({
                            "name": it.get('name', 'Reward'),
                            "image": img,
                            "minutes": int(it.get('requiredMinutes') or it.get('required_minutes') or 60)
                        })
                    
                    if rewards:
                        active_campaigns.append({
                            "campaign_name": camp.get('title') or camp.get('name'),
                            "start": camp.get('startAt') or camp.get('starts_at') or "2026-04-07",
                            "end": camp.get('endAt') or camp.get('ends_at') or "2026-05-04",
                            "rewards": rewards
                        })

        # --- FALLBACK: Falls JSON nichts lieferte, nutze HTML-Textsuche ---
        if not active_campaigns:
            print("Versuche HTML Fallback...")
            soup = BeautifulSoup(active_html, 'html.parser')
            # Suche nach Belohnungs-Karten über den Text "Watch Xh"
            watch_texts = soup.find_all(string=re.compile(r'Watch \d+', re.I))
            
            temp_rewards = []
            for wt in watch_texts:
                card = wt.find_parent(class_=re.compile(r'card|item|reward', re.I)) or wt.parent.parent
                img = card.find('img')
                name = card.find(['h3', 'h4', 'p', 'span'])
                
                if img:
                    img_url = img.get('src') or img.get('data-src') or ""
                    if img_url.startswith('/'): img_url = "https://twitchdrops.app" + img_url
                    
                    time_str = wt.strip()
                    mins = 60
                    nums = re.findall(r'\d+', time_str)
                    if nums:
                        val = int(nums[0])
                        mins = val * 60 if 'h' in time_str.lower() else val
                    
                    temp_rewards.append({
                        "name": name.get_text().strip() if name else "Loot Reward",
                        "image": img_url,
                        "minutes": mins
                    })

            if temp_rewards:
                active_campaigns.append({
                    "campaign_name": "Predecessor Premium Drops",
                    "start": "2026-04-07",
                    "end": "2026-05-04",
                    "rewards": temp_rewards
                })

    except Exception as e:
        print(f"Fehler: {e}")

    # Aktuelle deutsche Zeit (CEST) berechnen
    now_utc = datetime.now(timezone.utc)
    # CEST ist UTC+2
    german_time = now_utc + timedelta(hours=2)
    
    output = {
        "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
        "active": len(active_campaigns) > 0,
        "campaigns": active_campaigns
    }
    
    with open('drops.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"Abgeschlossen. Aktiv: {output['active']}")

if __name__ == "__main__":
    fetch_drops()
