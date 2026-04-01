import os
import requests
import json
import re
from groq import Groq
from datetime import datetime, timedelta

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHANNEL_ID = "1487129767865225261" 

def get_discord_messages():
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=25"
    res = requests.get(url, headers=headers)
    return res.json() if res.status_code == 200 else []

def find_deep_img(obj):
    """Recursively search for any image in standard msg, snapshots, or embeds."""
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

def force_iso_date(date_str, posted_date):
    """Converts AI output like 'April 7' into YYYY-MM-DD."""
    try:
        clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', str(date_str), flags=re.I)
        if not re.search(r'\d{4}', clean):
            clean += f" {datetime.now().year}"
        match = re.search(r'([a-zA-Z]+)\s+(\d+)\s+(\d{4})', clean)
        if match:
            mon, day, year = match.groups()
            dt = datetime.strptime(f"{mon[:3].capitalize()} {day} {year}", "%b %d %Y")
            return dt.strftime("%Y-%m-%d")
    except: pass
    return posted_date[:10]

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
    client = Groq(api_key=GROQ_API_KEY)
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""
    Today is {today}. Context: Predecessor Game Discord.
    Extract every event mentioned. 
    
    RULES:
    1. Create a short, UNIQUE title for each event (e.g., "V1.13 PATCH", "AURORA REVEAL"). 
    2. Identify the ACTUAL release date mentioned (YYYY-MM-DD).
    3. Return ONLY a JSON list.
    
    Messages: {messages_text}
    """
    try:
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        raw = chat.choices[0].message.content
        return json.loads(re.search(r'\[.*\]', raw, re.DOTALL).group(0))
    except: return []

def scrape():
    messages = get_discord_messages()
    master_list = []
    if messages:
        intel_pool = {}
        ai_input_list = []
        for m in messages:
            text = extract_full_content(m)
            img = find_deep_img(m) # RESTORED IMAGE SEARCH
            if text:
                intel_pool[m['id']] = {
                    "text": re.sub(r'<@&?\d+>', '', text).replace('🔔', '').strip(),
                    "posted": m['timestamp'],
                    "img": img,
                    "url": f"https://discord.com/channels/1055546338907017278/1487129767865225261/{m['id']}"
                }
                ai_input_list.append(f"ID: {m['id']} | CONTENT: {text}")

        ai_events = ask_groq("\n---\n".join(ai_input_list))
        for ae in ai_events:
            mid = ae.get('original_id')
            if mid in intel_pool:
                date = force_iso_date(ae.get('date', ''), intel_pool[mid]['posted'])
                title = ae.get('title', 'UPDATE').upper()
                etype = "patch" if "patch" in title.lower() else "news"
                if "twitch" in intel_pool[mid]['text'].lower() or "stream" in intel_pool[mid]['text'].lower():
                    etype = "twitch"
                
                master_list.append({
                    "date": date,
                    "iso_date": date + ("T18:00:00Z" if etype == "twitch" else "T00:00:00Z"),
                    "title": title,
                    "type": etype,
                    "desc": intel_pool[mid]['text'],
                    "image": intel_pool[mid]['img'],
                    "url": "https://www.twitch.tv/predecessorgame" if etype == "twitch" else intel_pool[mid]['url']
                })

    output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": master_list}
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)

if __name__ == "__main__":
    scrape()
