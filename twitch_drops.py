import json
import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

def fetch_drops():
    print("--- Synchronisiere Twitch Drops (Fix: HTML-Parser & Zeit) ---")
    
    url = "https://twitchdrops.app/game/predecessor"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    }

    active_campaigns = []

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Fehler: Seite konnte nicht geladen werden ({response.status_code})")
            return

        html = response.text
        # Wir trennen den HTML-Code bei "PAST DROPS" (Groß- Kleinschreibung egal)
        html_parts = re.split(r'PAST DROPS', html, flags=re.IGNORECASE)
        active_html = html_parts[0]
        
        # FIX: Hier wurde 'html.parser' statt 'parser' eingesetzt
        soup = BeautifulSoup(active_html, 'html.parser')
        
        # --- VERSUCH 1: JSON SCAN (Hintergrund-Daten) ---
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        
        if next_data_match:
            print("JSON-Daten gefunden. Suche Belohnungs-Listen...")
            full_json = json.loads(next_data_match.group(1))
            
            # Wir suchen im JSON nach Objekten, die eine Liste von Belohnungen haben
            def find_campaigns_recursive(obj):
                found = []
                if isinstance(obj, dict):
                    # Eine Kampagne erkennen wir an 'items' oder 'drops' und Predecessor-Bezug
                    is_pred = (obj.get('gameName') == 'Predecessor' or 
                               obj.get('game_id') == 515056 or 
                               'Predecessor' in str(obj.get('title', '')))
                    
                    if is_pred and (isinstance(obj.get('items'), list) or isinstance(obj.get('drops'), list)):
                        found.append(obj)
                    
                    for v in obj.values():
                        res = find_campaigns_recursive(v)
                        if res: found.extend(res)
                elif isinstance(obj, list):
                    for i in obj:
                        res = find_campaigns_recursive(i)
                        if res: found.extend(res)
                return found

            campaign_matches = find_campaigns_recursive(full_json)
            now = datetime.now(timezone.utc)

            for camp in campaign_matches:
                # Zeiträume bestimmen
                s_str = camp.get('starts_at') or camp.get('startAt') or camp.get('startsAt')
                e_str = camp.get('ends_at') or camp.get('endAt') or camp.get('endsAt')
                
                if not e_str: continue

                try:
                    e_dt = datetime.fromisoformat(e_str.replace('Z', '+00:00'))
                    
                    if e_dt > now:
                        print(f"Aktive Kampagne: {camp.get('name') or camp.get('title')}")
                        rewards = []
                        items = camp.get('items') or camp.get('drops') or []
                        for it in items:
                            img = it.get('image') or it.get('image_url') or ""
                            if img.startswith('/'): img = "https://twitchdrops.app" + img
                            
                            rewards.append({
                                "name": it.get('name', 'Belohnung'),
                                "image": img,
                                "minutes": int(it.get('required_minutes') or it.get('minutes', 60))
                            })
                        
                        if rewards:
                            active_campaigns.append({
                                "campaign_name": camp.get('name') or camp.get('title', 'Predecessor Drops'),
                                "start": s_str or "2026-04-07T18:00:00Z",
                                "end": e_str,
                                "rewards": rewards
                            })
                            break # Wir haben die Hauptkampagne gefunden
                except: continue

        # --- VERSUCH 2: HTML FALLBACK (Falls JSON nichts lieferte) ---
        if not active_campaigns:
            print("Versuche HTML-Parsing für Belohnungen...")
            watch_markers = soup.find_all(string=re.compile(r'Watch \d+', re.I))
            
            temp_rewards = []
            for wm in watch_markers:
                parent = wm.parent.parent
                for _ in range(4):
                    if parent.find('img'): break
                    parent = parent.parent
                
                img = parent.find('img')
                name_tag = parent.find(['h3', 'h4', 'p', 'span'], string=True)
                
                if img:
                    name = name_tag.get_text().strip() if name_tag else img.get('alt', 'Drop Item')
                    img_url = img.get('src') or img.get('data-src') or ""
                    if img_url.startswith('/'): img_url = "https://twitchdrops.app" + img_url
                    
                    # Zeit berechnen
                    time_str = wm.strip()
                    mins = 60
                    nums = re.findall(r'\d+', time_str)
                    if nums:
                        val = int(nums[0])
                        mins = val * 60 if 'h' in time_str.lower() else val
                    
                    if not any(r['name'] == name for r in temp_rewards):
                        temp_rewards.append({"name": name, "image": img_url, "minutes": mins})
            
            if temp_rewards:
                active_campaigns.append({
                    "campaign_name": "Predecessor Drops",
                    "start": "2026-04-07T18:00:00Z",
                    "end": "2026-05-04T18:00:00Z",
                    "rewards": temp_rewards
                })

    except Exception as e:
        print(f"Fehler: {e}")

    # CEST Zeitstempel (+2h)
    german_time = datetime.now(timezone.utc) + timedelta(hours=2)
    output = {
        "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
        "active": len(active_campaigns) > 0,
        "campaigns": active_campaigns
    }
    
    with open('drops.json', 'w') as f:
        json.dump(output, f, indent=4)
    print("Speichern erfolgreich beendet.")

if __name__ == "__main__":
    fetch_drops()
