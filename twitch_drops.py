import json
import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

def fetch_drops():
    print("--- Autonome Synchronisierung: TwitchDrops.app (Predecessor) ---")
    
    url = "https://twitchdrops.app/game/predecessor"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    }

    active_campaigns = []

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Fehler beim Laden der Seite: {response.status_code}")
            return

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        
        # Wir suchen den Next.js Datenblock
        next_data_script = soup.find('script', id='__NEXT_DATA__')
        
        if next_data_script:
            print("Analysiere Datenstruktur...")
            data = json.loads(next_data_script.string)
            
            # REKURSIVE SUCHE: Wir suchen im gesamten JSON nach Kampagnen-Objekten
            # Eine Kampagne erkennen wir an 'items' (Liste) und 'ends_at' / 'endsAt'
            def find_campaigns(obj):
                found = []
                if isinstance(obj, dict):
                    # Kriterium für eine Kampagne: Hat Items und ein Enddatum
                    if ('items' in obj or 'drops' in obj) and ('ends_at' in obj or 'endAt' in obj or 'endsAt' in obj):
                        found.append(obj)
                    for v in obj.values():
                        res = find_campaigns(v)
                        if res: found.extend(res)
                elif isinstance(obj, list):
                    for i in obj:
                        res = find_campaigns(i)
                        if res: found.extend(res)
                return found

            all_potential_campaigns = find_campaigns(data)
            now = datetime.now(timezone.utc)

            for camp in all_potential_campaigns:
                # Zeitraum bestimmen
                start_str = camp.get('starts_at') or camp.get('startAt') or camp.get('startsAt')
                end_str = camp.get('ends_at') or camp.get('endAt') or camp.get('endsAt')
                
                if not start_str or not end_str:
                    continue

                try:
                    # ISO-Format parsen (verschiedene Varianten abfangen)
                    start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    
                    # Nur Kampagnen nehmen, die AKTUELL laufen
                    if start_dt <= now <= end_dt:
                        print(f"Aktive Kampagne identifiziert: {camp.get('name') or camp.get('title')}")
                        
                        rewards = []
                        items = camp.get('items') or camp.get('drops') or []
                        for item in items:
                            img = item.get('image') or item.get('image_url') or ""
                            # Absolute URL sicherstellen
                            if img.startswith('/'): img = "https://twitchdrops.app" + img
                            
                            rewards.append({
                                "name": item.get('name', 'Belohnung'),
                                "image": img,
                                "minutes": int(item.get('required_minutes') or item.get('minutes') or 60)
                            })
                        
                        if rewards:
                            active_campaigns.append({
                                "campaign_name": camp.get('name') or camp.get('title', 'Predecessor Drops'),
                                "start": start_str,
                                "end": end_str,
                                "rewards": rewards
                            })
                except Exception as e:
                    print(f"Fehler beim Zeit-Parsing einer Kampagne: {e}")

        # --- FALLBACK: DYNAMISCHES HTML PARSING (Falls JSON-Struktur sich komplett ändert) ---
        if not active_campaigns:
            print("JSON-Suche nicht erfolgreich. Nutze dynamisches HTML-Scanning...")
            # Wir suchen Belohnungskarten im aktiven Bereich (vor "PAST DROPS")
            active_html = re.split(r'PAST DROPS', html, flags=re.IGNORECASE)[0]
            active_soup = BeautifulSoup(active_html, 'html.parser')
            
            # Wir nutzen die "Watch Xh"-Texte als Anker für Belohnungen
            watch_markers = active_soup.find_all(string=re.compile(r'Watch \d+', re.I))
            
            temp_rewards = []
            for marker in watch_markers:
                # Navigiere zum Karten-Container hoch (flexibel)
                parent = marker.parent
                card = None
                for _ in range(5):
                    if parent.find('img') and parent.find(re.compile('h[1-6]|p|span', re.I)):
                        card = parent
                        break
                    parent = parent.parent
                
                if card:
                    img = card.find('img')
                    name_tag = card.find(re.compile('h[1-6]|p|span', re.I))
                    
                    if img and name_tag:
                        # Zeit berechnen
                        time_text = marker.strip()
                        mins = 60
                        digits = re.findall(r'\d+', time_text)
                        if digits:
                            val = int(digits[0])
                            mins = val * 60 if 'h' in time_text.lower() else val
                        
                        img_url = img.get('src') or img.get('data-src', '')
                        if img_url.startswith('/'): img_url = "https://twitchdrops.app" + img_url

                        reward_name = name_tag.get_text().strip()
                        if not any(r['name'] == reward_name for r in temp_rewards):
                            temp_rewards.append({
                                "name": reward_name,
                                "image": img_url,
                                "minutes": mins
                            })
            
            if temp_rewards:
                active_campaigns.append({
                    "campaign_name": "Active Twitch Drops",
                    "start": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "rewards": temp_rewards
                })

    except Exception as e:
        print(f"Allgemeiner Scrape-Fehler: {e}")

    # Zeitstempel für die Webseite (Deutschland)
    german_time = datetime.now(timezone.utc) + timedelta(hours=2)
    output = {
        "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
        "active": len(active_campaigns) > 0,
        "campaigns": active_campaigns
    }
    
    with open('drops.json', 'w') as f:
        json.dump(output, f, indent=4)
    
    print(f"Speichern beendet. Aktiv: {output['active']}")

if __name__ == "__main__":
    fetch_drops()
