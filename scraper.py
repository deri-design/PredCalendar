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
    if not obj: return ""
    if isinstance(obj, str):
        if any(ext in obj.lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']) and 'http' in obj:
            return obj
    if isinstance(obj, dict):
        for key in ['url', 'proxy_url']:
            if key in obj and isinstance(obj[key], str) and any(ext in obj[key].lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                return obj[key]
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
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    Today is {today}. Context: "Predecessor" game announcements.
    Identify ACTUAL release/event dates and short titles. 
    RULES:
    1. Only return events with specific dates. 
    2. Format: JSON list only. date: YYYY-MM-DD. title: short. original_id: match to ID. type: patch/hero/season/twitch.
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
    print("Starting Sanitized Deduplication Scrape...")
    messages = get_discord_messages()
    if not messages: return

    intel_pool = {}
    ai_input_list = []
    for m in messages:
        text = extract_full_content(m)
        img = find_deep_img(m)
        if text:
            # We explicitly link the image to the Message ID here
            intel_pool[m['id']] = {
                "text": clean_discord_text(text), 
                "img": img, 
                "url": f"https://discord.com/channels/1055546338907017278/{CHANNEL_ID}/{m['id']}"
            }
            ai_input_list.append(f"ID: {m['id']} | CONTENT: {text}")

    try:
        ai_events = ask_groq("\n---\n".join(ai_input_list))
        
        # Load Existing to maintain historical data
        try:
            with open('events.json', 'r') as f:
                old_data = json.load(f)
                master_list = old_data.get('events', [])
        except: master_list = []

        # Process new events found by AI
        for ae in ai_events:
            mid = ae.get('original_id')
            if mid in intel_pool:
                full_text = intel_pool[mid]['text'].lower()
                etype = ae['type']
                eurl = intel_pool[mid]['url']
                if any(x in full_text for x in ["twitch", "stream"]):
                    etype, eurl = "twitch", "https://www.twitch.tv/predecessorgame"
                
                iso = ae.get('iso_date', ae['date'] + ("T18:00:00Z" if etype == "twitch" else "T00:00:00Z"))

                # Create the entry. Noticeae['image'] is now forced from intel_pool[mid]['img']
                new_obj = {
                    "date": ae['date'], "iso_date": iso, "title": ae['title'].strip().upper(), "type": etype,
                    "desc": intel_pool[mid]['text'], "url": eurl, "image": intel_pool[mid]['img']
                }
                master_list.append(new_obj)

        # --- ADVANCED DEDUPLICATION ENGINE ---
        def get_fingerprint(event):
            # Normalizes title: "V1.13: THRONE" -> "THRONE"
            t = event['title'].upper()
            t = re.sub(r'V\d+\.\d+(\.\d+)?', '', t) # Remove version numbers
            t = re.sub(r'[^A-Z]', '', t) # Remove everything but letters
            return f"{event['date']}_{t}"

        unique_map = {}
        # Sort so we process items with images first
        master_list.sort(key=lambda x: (len(x.get('image', '')), len(x['title'])), reverse=True)

        for e in master_list:
            fingerprint = get_fingerprint(e)
            if fingerprint not in unique_map:
                unique_map[fingerprint] = e
            else:
                # Merge: Keep the one with the image if the existing one doesn't have it
                if not unique_map[fingerprint].get('image') and e.get('image'):
                    unique_map[fingerprint]['image'] = e['image']
                # Keep the longer description
                if len(e.get('desc', '')) > len(unique_map[fingerprint].get('desc', '')):
                    unique_map[fingerprint]['desc'] = e['desc']

        final_events = sorted(list(unique_map.values()), key=lambda x: x['date'])

        # Final cleanup: Remove old events and items without descriptions
        final_events = [e for e in final_events if e.get('desc') and e['date'] >= "2026-02-01"]

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": final_events}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Sync complete. {len(final_events)} unique operations stored.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
