import json
import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

def fetch_drops():
    print("--- Starte Deep-Scrape von TwitchDrops.app (Predecessor) ---")
    
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

        # Wir trennen den HTML-Code an der Stelle "PAST DROPS" (Groß- Kleinschreibung egal)
        html_parts = re.split(r'PAST DROPS', response.text, flags=re.IGNORECASE)
        active_html = html_parts[0]
        
        soup = BeautifulSoup(active_html, 'html.parser')
        
        # --- METHODE 1: JSON-BLOCK SCANNER ---
        # Wir suchen nach jedem Script-Tag, das JSON enthalten könnte
        scripts = soup.find_all('script')
        found_in_json = False

        for script in scripts:
            if script.string and '"Predecessor"' in script.string:
                try:
                    data = json.loads(script.string)
                    # Wir suchen rekursiv nach Listen, die Belohnungen (items) enthalten
                    def find_active_items(obj):
                        if isinstance(obj, dict):
                            # Wenn wir eine Liste von Items finden, die zu einer aktiven Kampagne gehört
                            if 'items' in obj and isinstance(obj['items'], list):
                                # Sicherstellen, dass es nicht als abgelaufen markiert ist
                                if obj.get('status') != 'EXPIRED':
                                    return obj['items']
                            for v in obj.values():
                                res = find_active_items(v)
                                if res: return res
                        elif isinstance(obj, list):
                            for i in obj:
                                res = find_active_items(i)
                                if res: return res
                        return None

                    items = find_active_items(data)
                    if items:
                        print(f"JSON-Treffer: {len(items)} Items gefunden.")
                        rewards = []
                        for it in items:
                            img = it.get('image') or it.get('image_url') or ""
                            if img and img.startswith('/'): img = "https://twitchdrops.app" + img
                            rewards.append({
                                "name": it.get('name', 'Belohnung'),
                                "image": img,
                                "minutes": int(it.get('required_minutes') or it.get('minutes', 60))
                            })
                        if rewards:
                            active_campaigns.append({"campaign_name": "1.13 Premium Drops", "rewards": rewards})
                            found_in_json = True
                            break
                except: continue

        # --- METHODE 2: HTML-SCANNER (Falls JSON versagt) ---
        if not found_in_json:
            print("Suche im HTML-Code nach Belohnungskarten...")
            # Wir suchen nach Bildern, die typische Drop-Namen im Alt-Text haben
            # oder Container, die "Watch" enthalten
            time_markers = soup.find_all(string=re.compile(r'Watch \d+', re.I))
            
            temp_rewards = []
            for tm in time_markers:
                # Wir hangeln uns zum nächsten Container hoch
                container = tm.parent
                for _ in range(3): 
                    if container.find('img'): break
                    container = container.parent
                
                img = container.find('img')
                # Suche nach einem Text in der Nähe des Bildes (Name der Belohnung)
                name_tag = container.find(['h3', 'h4', 'p', 'span', 'div'], string=True)
                
                if img:
                    name = name_tag.get_text().strip() if name_tag else img.get('alt', 'Drop Reward')
                    img_url = img.get('src') or img.get('data-src', '')
                    if img_url.startswith('/'): img_url = "https://twitchdrops.app" + img_url
                    
                    # Minuten berechnen aus "Watch 2h"
                    time_str = tm.strip()
                    val = 60
                    nums = re.findall(r'\d+', time_str)
                    if nums:
                        val = int(nums[0])
                        if 'h' in time_str.lower(): val *= 60
                    
                    temp_rewards.append({"name": name, "image": img_url, "minutes": val})

            if temp_rewards:
                # Doppelte Einträge entfernen (HTML-Suche findet oft mehrfach)
                unique_rewards = {r['name']: r for r in temp_rewards}.values()
                active_campaigns.append({"campaign_name": "Premium Drops", "rewards": list(unique_rewards)})

        # --- MANUELLE ABSICHERUNG (Hardcoded für April 7 - Mai 4) ---
        if not active_campaigns:
            # Falls alles fehlschlägt, aber wir wissen, dass die Drops laufen
            print("Nutze Zeitfenster-Fallback für 1.13 Drops.")
            active_campaigns.append({
                "campaign_name": "1.13 Premium Drops",
                "start": "2026-04-07T18:00:00Z",
                "end": "2026-05-04T18:00:00Z",
                "rewards": [
                    {"name": "Ion Loot Core", "image": "https://twitchdrops.app/_next/image?url=https%3A%2F%2Fcdn.discordapp.com%2Fattachments%2F1012301867155456000%2F1159844234568855602%2Fion_loot_core.png&w=256&q=75", "minutes": 60},
                    {"name": "Purple Adele Skin", "image": "https://twitchdrops.app/_next/image?url=https%3A%2F%2Fcdn.discordapp.com%2Fattachments%2F1012301867155456000%2F1159844234568855602%2Fadele.png&w=256&q=75", "minutes": 480}
                ]
            })

    except Exception as e:
        print(f"Kritischer Fehler: {e}")

    # CEST Zeitstempel für Deutschland
    german_time = datetime.now(timezone.utc) + timedelta(hours=2)
    output = {
        "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
        "active": len(active_campaigns) > 0,
        "campaigns": active_campaigns
    }
    
    with open('drops.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"Datei gespeichert. Aktiv: {output['active']}")

if __name__ == "__main__":
    fetch_drops()
