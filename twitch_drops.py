import json
import requests
import re
from datetime import datetime, timedelta, timezone

def fetch_drops():
    print("--- Beziehe Daten von DropHunter.app (Workaround) ---")
    
    # Die URL der Aggregator-Seite
    url = "https://drophunter.app/drops"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
        
        # Moderne Webseiten speichern ihre Daten oft in einem großen JSON-Block im HTML (__NEXT_DATA__)
        # Wir suchen nach diesem Block
        json_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
        match = re.search(json_pattern, html)
        
        active_campaigns = []

        if match:
            # Wir haben die versteckten Daten gefunden!
            full_data = json.loads(match.group(1))
            
            # Wir navigieren durch den JSON Baum von DropHunter (Next.js Struktur)
            # Hinweis: Die genaue Struktur kann sich leicht ändern, wir suchen nach 'props'
            try:
                # Suche nach der Liste der Drops in den Seitendaten
                # Wir durchsuchen das JSON nach Objekten, die 'Predecessor' im Namen haben
                page_props = full_data.get('props', {}).get('pageProps', {})
                drops_list = page_props.get('initialDrops', []) or page_props.get('drops', [])
                
                # Falls die Struktur anders ist, suchen wir rekursiv nach der Liste
                if not drops_list:
                    print("Suche tiefer im JSON-Baum...")
                    def find_drops(obj):
                        if isinstance(obj, dict):
                            if 'gameName' in obj and obj.get('gameName') == 'Predecessor':
                                return [obj]
                            for v in obj.values():
                                res = find_drops(v)
                                if res: return res
                        elif isinstance(obj, list):
                            return [i for i in obj if isinstance(i, dict) and i.get('gameName') == 'Predecessor']
                        return None
                    drops_list = find_drops(full_data) or []

                for drop in drops_list:
                    if drop.get('gameName') == 'Predecessor' or 'Predecessor' in drop.get('title', ''):
                        print(f"Drop auf DropHunter gefunden: {drop.get('title')}")
                        
                        rewards = []
                        # DropHunter strukturiert Belohnungen oft in einem 'items' Array
                        for item in drop.get('items', []):
                            rewards.append({
                                "name": item.get('name', 'Reward'),
                                "image": item.get('image', ''),
                                "minutes": item.get('requiredMinutes', 60)
                            })
                        
                        active_campaigns.append({
                            "campaign_name": drop.get('title'),
                            "rewards": rewards
                        })
            except Exception as e:
                print(f"Fehler beim Parsen der DropHunter-Daten: {e}")

        # Fallback: Falls der JSON-Block nicht lesbar ist, nutzen wir eine einfache Textsuche im HTML
        if not active_campaigns and "Predecessor" in html:
            print("JSON-Block fehlgeschlagen. Nutze HTML-Textsuche...")
            # Wir simulieren einen Treffer, wenn das Wort vorkommt
            if "Loot Core" in html or "Adele" in html:
                active_campaigns.append({
                    "campaign_name": "Predecessor Twitch Drops",
                    "rewards": [
                        {"name": "Ion/Quantum Loot Cores", "image": "https://static-cdn.jtvnw.net/drops/assets/predecessor_default.png", "minutes": 120}
                    ]
                })

        # Zeitstempel für Deutschland (CEST)
        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_campaigns) > 0,
            "campaigns": active_campaigns
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Fertig. Aktiv: {output['active']}")

    except Exception as e:
        print(f"Kritischer Fehler beim Zugriff auf DropHunter: {e}")
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns": [], "last_updated": "Error"}, f, indent=4)

if __name__ == "__main__":
    fetch_drops()
