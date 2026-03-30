import os
import requests
import json
import re
from groq import Groq
from datetime import datetime

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
CHANNEL_ID = "1487129767865225261" 

def get_discord_messages():
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=25"
    res = requests.get(url, headers=headers)
    return res.json() if res.status_code == 200 else []

def find_deep_img(obj):
    if isinstance(obj, str):
        if any(ext in obj.lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']):
            if 'http' in obj: return obj
    if isinstance(obj, dict):
        if 'image' in obj and isinstance(obj['image'], dict):
            url = obj['image'].get('url')
            if url: return url
        for v in obj.values():
            res = find_deep_img(v)
            if res: return res
    if isinstance(obj, list):
        for i in obj:
            res = find_deep_img(i)
            if res: return res
    return ""

def clean_discord_text(text):
    text = re.sub(r'<@&?\d+>', '', text)
    text = text.replace('🔔', '')
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()

def extract_full_content(m):
    text = m.get('content', '')
    if 'message_snapshots' in m:
        for snap in m['message_snapshots']:
            msg = snap.get('message', {})
            text += f"\n{msg.get('content', '')}"
            for emb in msg.get('embeds', []):
                text += f"\n{emb.get('title', '')}\n{emb.get('description', '')}"
    if 'embeds' in m:
        for emb in m['embeds']:
            text += f"\n{emb.get('title', '')}\n{emb.get('description', '')}"
    return text.strip()

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_KEY)
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""
    Today is {today}. Context: "Predecessor" game announcements.
    Identify ACTUAL release/event dates and short titles. 
    Format: JSON list only. date: YYYY-MM-DD. title: short. original_id: match to ID. type: patch/hero/season/twitch.
    Messages: {messages_text}
    """
    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.1
    )
    raw = chat.choices[0].message.content
    return json.loads(re.search(r'\[.*\]', raw, re.DOTALL).group(0))

def scrape():
    print("Starting Persistent Logic Scrape...")
    messages = get_discord_messages()
    if not messages: return

    intel_pool = {}
    ai_input_list = []
    for m in messages:
        text = extract_full_content(m)
        img = find_deep_img(m)
        if text:
            intel_pool[m['id']] = {
                "text": clean_discord_text(text),
                "img": img, 
                "url": f"https://discord.com/channels/1055546338907017278/{CHANNEL_ID}/{m['id']}"
            }
            ai_input_list.append(f"ID: {m['id']} | CONTENT: {text}")

    try:
        ai_events = ask_groq("\n---\n".join(ai_input_list))
        
        # Load existing events to prevent disappearing items
        try:
            with open('events.json', 'r') as f:
                old_data = json.load(f)
                new_events = old_data.get('events', [])
        except:
            new_events = []

        for ae in ai_events:
            mid = ae.get('original_id')
            if mid in intel_pool:
                # --- HARD LOGIC OVERRIDES ---
                # 1. Twitch Categorization
                full_text = intel_pool[mid]['text'].lower()
                event_type = ae['type']
                event_url = intel_pool[mid]['url']

                if "twitch.tv" in full_text or "stream" in full_text or "twitch" in full_text:
                    event_type = "twitch"
                    event_url = "https://www.twitch.tv/predecessorgame"
                
                # 2. ISO Date Fix (Force 18:00 if Twitch Stream)
                iso = ae.get('iso_date', ae['date'] + "T00:00:00Z")
                if event_type == "twitch" and "18:00" not in iso:
                    iso = ae['date'] + "T18:00:00Z"

                event_obj = {
                    "date": ae['date'], "iso_date": iso, "title": ae['title'], "type": event_type,
                    "desc": intel_pool[mid]['text'], "url": event_url, "image": intel_pool[mid]['img']
                }

                # Update if exists, otherwise append
                existing_idx = next((i for i, x in enumerate(new_events) if x['title'] == ae['title']), -1)
                if existing_idx > -1:
                    new_events[existing_idx] = event_obj
                else:
                    new_events.append(event_obj)

        # Remove very old events (older than 3 months) to keep file clean
        cutoff = (datetime.now().replace(day=1)).strftime("%Y-%m-%d")
        new_events = [e for e in new_events if e['date'] >= "2026-01-01"]

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": new_events}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print("Success: Database Merged and twitch logic enforced.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
