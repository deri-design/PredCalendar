import json
import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

def fetch_drops():
    print("--- Beziehe NUR AKTIVE Belohnungen (Stabiler Filter-Modus) ---")
    
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

        # Wir trennen den HTML-Code an der Stelle "PAST DROPS"
        # Alles was danach kommt, wird ignoriert.
        html_parts = re.split(r'PAST DROPS', response.text, flags=re.IGNORECASE)
        active_html = html_parts[0]
        
        soup = BeautifulSoup(active_html, 'html.parser')
        
        # 1. VERSUCH: Auslesen aus den Metadaten (JSON)
        # Wir suchen den gesamten Original-Quelltext nach dem JSON-Block ab
        full_soup = BeautifulSoup(response.text, 'html.parser')
        next_data = full_soup.find('script', id='__NEXT_DATA__')
        
        if next_data:
            print("Analysiere JSON-Struktur...")
            data = json.loads(next_data.string)
            page_props = data.get('props', {}).get('pageProps', {})
            game_obj = page_props.get('game', {})
            
            raw_campaigns = game_obj.get('drop_campaigns', []) or page_props.get('campaigns', [])
            
            for camp in raw_campaigns:
                # Wir nehmen nur Kampagnen mit Status ACTIVE oder die wirklichen Premium Drops
                status = str(camp.get('status', '')).upper()
                if status == 'ACTIVE' or 'Premium' in camp.get('name', ''):
                    print(f"Aktive Kampagne gefunden: {camp.get('name')}")
                    rewards = []
                    for item in camp.get('items', []):
                        img = item.get('image', '')
                        if img and img.startswith('/'): img = "https://twitchdrops.app" + img
                        
                        rewards.append({
                            "name": item.get('name', 'Belohnung'),
                            "image": img,
                            "minutes": item.get('required_minutes') or item.get('minutes', 60)
                        })
                    
                    if rewards:
                        active_campaigns.append({
                            "campaign_name": camp.get('name'),
                            "rewards": rewards
                        })

        # 2. VERSUCH: Falls JSON nichts lieferte, nutze das gefilterte HTML-Parsing
        if not active_campaigns:
            print("Suche Belohnungen im aktiven HTML-Bereich...")
            # Wir suchen nach Containern, die "Watch" enthalten
            time_elements = soup.find_all(string=re.compile(r'Watch \d+', re.I))
            
            temp_rewards = []
            for te in time_elements:
                parent = te.parent.parent
                img_tag = parent.find('img')
                name_tag = parent.find(['h3', 'h4', 'p', 'span'], string=True)
                
                if img_tag:
                    name = name_tag.get_text().strip() if name_tag else img_tag.get('alt', 'Drop Item')
                    img_url = img_tag['src'] if img_tag.has_attr('src') else ""
                    if img_url.startswith('/'): img_url = "https://twitchdrops.app" + img_url
                    
                    # Minuten berechnen
                    time_str = te.strip()
                    mins = 60
                    nums = re.findall(r'\d+', time_str)
                    if nums:
                        val = int(nums[0])
                        mins = val * 60 if 'h' in time_str.lower() else val

                    temp_rewards.append({"name": name, "image": img_url, "minutes": mins})
            
            if temp_rewards:
                active_campaigns.append({
                    "campaign_name": "Aktuelle Drops",
                    "rewards": temp_rewards
                })

    except Exception as e:
        print(f"Fehler während der Extraktion: {e}")

    # CEST Zeitstempel (+2h von UTC)
    german_time = datetime.now(timezone.utc) + timedelta(hours=2)
    output = {
        "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
        "active": len(active_campaigns) > 0,
        "campaigns": active_campaigns
    }
    
    with open('drops.json', 'w') as f:
        json.dump(output, f, indent=4)
    
    print(f"Ergebnis gespeichert. Aktiv: {output['active']}")

if __name__ == "__main__":
    fetch_drops()
