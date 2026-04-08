import json
import requests
import uuid
from datetime import datetime, timedelta, timezone

def fetch_drops():
    print("--- Starte Twitch Drops Sync (Klartext-Modus ohne Hash) ---")
    
    url = "https://gql.twitch.tv/gql"
    
    # Wir generieren eine zufällige Geräte-ID, um wie ein neuer Browser auszusehen
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", # Offizielle Twitch-Web-ID
        "X-Device-Id": uuid.uuid4().hex,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://www.twitch.tv",
        "Referer": "https://www.twitch.tv/drops/campaigns"
    }
    
    # Die Klartext-Abfrage für die Datenbank (funktioniert ohne SHA-Hash)
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
    
    payload = {"query": query}

    try:
        # Anfrage an Twitch senden
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if res.status_code != 200:
            print(f"Fehler: Twitch hat die Anfrage abgelehnt (Status {res.status_code})")
            return

        data = res.json()
        all_campaigns = data.get("data", {}).get("dropCampaigns", [])
        
        if not all_campaigns:
            print("Warnung: Twitch hat 0 Kampagnen zurückgegeben. Bot-Schutz evtl. aktiv.")
            return

        print(f"Erfolg: {len(all_campaigns)} globale Kampagnen gescannt.")
        
        active_predecessor_drops = []
        now = datetime.now(timezone.utc)

        for camp in all_campaigns:
            game = camp.get("game") or {}
            # Wir suchen nach Predecessor (ID: 515056)
            if game.get("id") == "515056" or "Predecessor" in game.get("name", ""):
                
                # Zeitfenster prüfen (da der Status 'ACTIVE' oft verzögert ist)
                is_active = (camp.get('status') == "ACTIVE")
                
                if not is_active:
                    try:
                        start = datetime.strptime(camp['startAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        end = datetime.strptime(camp['endAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        if start <= now <= end:
                            is_active = True
                    except: pass

                if is_active:
                    print(f"AKTIVE DROPS GEFUNDEN: {camp['name']}")
                    rewards = []
                    for drop in camp.get("timeBasedDrops", []):
                        for edge in drop.get("benefitEdges", []):
                            benefit = edge.get("benefit", {})
                            rewards.append({
                                "name": benefit.get("name") or drop.get("name"),
                                "image": benefit.get("imageAssetURL") or "https://static-cdn.jtvnw.net/drops/assets/predecessor_default.png",
                                "minutes": drop.get("requiredMinutesWatched")
                            })
                    
                    active_predecessor_drops.append({
                        "campaign_name": camp['name'],
                        "rewards": rewards
                    })

        # Zeitstempel für Deutschland (UTC+2 / CEST)
        german_time = datetime.now(timezone.utc) + timedelta(hours=2)
        output = {
            "last_updated": german_time.strftime("%Y-%m-%d %H:%M:%S") + " (CEST)",
            "active": len(active_predecessor_drops) > 0,
            "campaigns": active_predecessor_drops
        }
        
        with open('drops.json', 'w') as f:
            json.dump(output, f, indent=4)
            
        print(f"Datei gespeichert. Aktiv: {output['active']}")

    except Exception as e:
        print(f"Kritischer Fehler: {e}")
        # Notfall-Datei schreiben, damit die Website nicht abstürzt
        with open('drops.json', 'w') as f:
            json.dump({"active": False, "campaigns": [], "last_updated": "Error"}, f, indent=4)

if __name__ == "__main__":
    fetch_drops()
