import json
import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

def fetch_drops():
    print("--- Suche Predecessor Drops (Greedy Search Mode) ---")
    
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

        html = response.text
        # Filtere den Bereich vor "PAST DROPS"
        active_html = re.split(r'PAST DROPS', html, flags=re.IGNORECASE)[0]
        soup = BeautifulSoup(active_html, 'html.parser')
        
        # --- METHODE: TOTALER JSON SCAN ---
        # Wir suchen nach dem __NEXT_DATA__ Block
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        
        if next_data_match:
            print("Analysiere Daten-Haufen...")
            full_json = json.loads(next_data_match.group(1))
            
            # Wir suchen im gesamten JSON nach Objekten, die Predecessor-Daten enthalten
            def find_campaigns_everywhere(obj):
                found = []
                if isinstance(obj, dict):
                    # Wenn dieses Objekt 'items' und ein Datum hat, ist es eine Kampagne
                    if ('items' in obj or 'drops' in obj) and ('ends_at' in obj or 'endAt' in obj or 'endsAt' in obj):
                        # Prüfen ob Predecessor Bezug da ist (ID oder Name)
                        json_str = json.dumps(obj)
                        if "515056" in json_str or "Predecessor" in json_str:
                            found.append(obj)
                    for v in obj.values():
                        res = find_campaigns_everywhere(v)
                        if res: found.extend(res)
                elif isinstance(obj, list):
                    for i in obj:
                        res = find_campaigns_everywhere(i)
                        if res: found.extend(res)
                return found

            campaign_matches = find_campaigns_everywhere(full_json)
            now = datetime.now(timezone.utc)

            for camp in campaign_matches:
                # Zeitraum bestimmen
                s_str = camp.get('starts_at') or camp.get('startAt') or camp.get('startsAt')
                e_str = camp.get('ends_at') or camp.get('endAt') or camp.get('endsAt')
                
                if not s_str or not e_str: continue

                try:
                    # Zeit-Strings säubern und parsen
                    s_dt = datetime.fromisoformat(s_str.replace('Z', '+00:00'))
                    e_dt = datetime.fromisoformat(e_str.replace('Z', '+00:00'))
                    
                    if s_dt <= now <= e_dt:
                        print(f"Aktive Kampagne gefunden: {camp.get('name') or camp.get('title')}")
                        rewards = []
                        items = camp.get('items') or camp.get('drops') or []
                        for it in items:
                            img = it.get('image') or it.get('image_url') or ""
                            if img.startswith('/'): img = "https://twitchdrops.app" + img
                            
                            rewards.append({
                                "name": it.get('name', 'Reward'),
                                "image": img,
                                "minutes": int(it.get('required_minutes') or it.get('minutes', 60))
                            })
                        
                        if rewards:
                            active_campaigns.append({
                                "campaign_name": camp.get('name') or camp.get('title', 'Predecessor Drops'),
                                "start": s_str,
                                "end": e_str,
                                "rewards": rewards
                            })
                except: continue

        # --- FALLBACK: HTML SCANNER ---
        if not active_campaigns:
            print("JSON-Scan ergebnislos. Starte HTML-Analyse...")
            # Wir suchen Belohnungskarten über den "Watch"-Text
            watch_labels = soup.find_all(string=re.compile(r'Watch \d+', re.I))
            temp_rewards = []
            for wl in watch_labels:
                card = wl.find_parent(class_=re.compile(r'card|item|reward', re.I)) or wl.parent.parent
                img = card.find('img')
                name_tag = card.find(['h3', 'h4', 'p', 'span'])
                
                if img:
                    img_url = img.get('src') or img.get('data-src') or ""
                    if img_url.startswith('/'): img_url = "https://twitchdrops.app" + img_url
                    
                    time_text = wl.strip()
                    val = 60
                    nums = re.findall(r'\d+', time_text)
                    if nums:
                        val = int(nums[0])
                        if 'h' in time_text.lower(): val *= 60
                    
                    temp_rewards.append({
                        "name": name_tag.get_text().strip() if name_tag else "Loot Reward",
                        "image": img_url,
                        "minutes": val
                    })
            
            if temp_rewards:
                # Dubletten filtern
                unique = {r['name']: r for r in temp_rewards}.values()
                active_campaigns.append({
                    "campaign_name": "Predecessor Drops",
                    "start": "2026-04-07T18:00:00Z",
                    "end": "2026-05-04T18:00:00Z",
                    "rewards": list(unique)
                })

    except Exception as e:
        print(f"Fehler: {e}")

    # Zeitstempel für die Website (CEST)
    german_time = datetime.now(timezone.utc) + timedelta(hours=2)
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
