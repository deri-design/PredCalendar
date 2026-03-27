import os
import requests
import json
import re
from datetime import datetime, timedelta

# Config
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "1487129767865225261"

def get_discord_messages():
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=15"
    res = requests.get(url, headers=headers)
    return res.json() if res.status_code == 200 else []

def brute_force_dates(messages):
    """Fallback: Manual scan if AI fails"""
    events = []
    for m in messages:
        content = m['content']
        # Look for simple dates like April 10
        match = re.search(r'([A-Z][a-z]+)\s+(\d{1,2})', content)
        if match:
            mon, day = match.groups()
            try:
                # Assume current year
                year = datetime.now().year
                dt = datetime.strptime(f"{mon[:3].capitalize()} {day} {year}", "%b %d %Y")
                events.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "title": content[:30] + "...",
                    "type": "news",
                    "url": f"https://discord.com/channels/1055546338907017278/{CHANNEL_ID}/{m['id']}"
                })
            except: pass
    return events

def ask_gemini(messages_text):
    # Using v1beta which is the most compatible endpoint for 1.5-flash
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"Today is {today}. Extract game events for 'Predecessor' from these messages. Return ONLY a JSON list: [{{'date': 'YYYY-MM-DD', 'title': 'name', 'type': 'patch/news', 'url': 'link', 'image': 'img'}}]. Text: {messages_text}"
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(api_url, json=payload, timeout=15)
        data = response.json()
        
        if "candidates" in data:
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
            return json.loads(json_match.group(0))
    except Exception as e:
        print(f"AI Step Failed: {e}")
    return None

def scrape():
    print("--- Temporal Sync: V1Beta Mode ---")
    messages = get_discord_messages()
    if not messages:
        print("Empty Discord results.")
        return

    combined = ""
    for m in messages:
        combined += f"SENT: {m['timestamp']} | MSG: {m['content']}\n---\n"

    print("Requesting Gemini (v1beta/1.5-flash)...")
    events = ask_gemini(combined)
    
    # If Gemini failed or found nothing, use manual regex scanner
    if not events:
        print("AI returned nothing. Using manual scanner fallback...")
        events = brute_force_dates(messages)

    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "events": events
    }
    
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"SUCCESS: {len(events)} events ready.")

if __name__ == "__main__":
    scrape()
