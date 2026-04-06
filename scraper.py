import os
import requests
import json
import re
from groq import Groq
from datetime import datetime

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
    return ""

def extract_intel(m):
    content = m.get('content', '')
    # 1. Grab Discord's Dynamic Timestamp: <t:123456789:R>
    ts_match = re.search(r'<t:(\d+):[A-Za-z]>', content)
    unix_ts = ts_match.group(1) if ts_match else None

    # 2. Extract Links
    urls = re.findall(r'(https?://[^\s]+)', content)
    for emb in m.get('embeds', []):
        if emb.get('url'): urls.append(emb['url'])
    
    # 3. Clean Text
    clean = re.sub(r'<@&?\d+>', '', content).replace('🔔', '')
    clean = re.sub(r'<t:\d+:[A-Za-z]>', '', clean) # Remove timestamp code from description
    
    return clean.strip(), urls, unix_ts

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_API_KEY)
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""
    Today is {today}. Context: Predecessor game announcements.
    Identify ACTUAL release/event dates and version numbers (e.g. V1.13).
    
    RULES:
    1. If the text mentions a date, output it.
    2. Identify the VERSION number if present.
    3. Return ONLY a JSON list of objects: [{{"idx": 0, "date": "YYYY-MM-DD", "version": "V1.xx", "title": "..."}}]
    
    Messages:
    {messages_text}
    """
    try:
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        return json.loads(re.search(r'\[.*\]', chat.choices[0].message.content, re.DOTALL).group(0))
    except: return []

def scrape():
    messages = get_discord_messages()
    if not messages: return

    try:
        with open('events.json', 'r') as f:
            old_db = json.load(f).get('events', [])
    except: old_db = []

    existing_ids = [str(e.get('original_id')) for e in old_db]
    to_process = []
    ai_input = ""
    
    for i, m in enumerate(messages):
        if str(m['id']) in existing_ids: continue
        
        clean_text, urls, unix_ts = extract_intel(m)
        to_process.append({
            "id": m['id'], "clean": clean_text, "urls": urls, "unix": unix_ts,
            "img": find_deep_img(m), "posted": m['timestamp'][:10]
        })
        ai_input += f"BLOCK_INDEX: {len(to_process)-1}\nCONTENT: {clean_text}\n---\n"

    if not to_process: return

    ai_results = ask_groq(ai_input)
    new_entries = []

    for ar in ai_results:
        idx = ar.get('idx')
        if idx is None or idx >= len(to_process): continue
        intel = to_process[idx]
        
        # Date Logic: Discord Unix Timestamp > AI Date > Post Date
        date = ar.get('date') or intel['posted']
        iso = date + "T15:00:00Z"
        if intel['unix']:
            # Use the EXACT Discord timestamp if found
            iso = datetime.fromtimestamp(int(intel['unix'])).strftime('%Y-%m-%dT%H:%M:%SZ')
            date = iso[:10]

        # Link/Type Logic
        etype = ar.get('type', 'news')
        eurl = "https://www.predecessorgame.com/en-US/news"
        yt = next((u for u in intel['urls'] if "youtube" in u or "youtu.be" in u), None)
        pp = next((u for u in intel['urls'] if "playp.red" in u), None)

        if "twitch" in intel['clean'].lower(): etype, eurl = "twitch", "https://www.twitch.tv/predecessorgame"
        elif yt: etype, eurl = "youtube", yt
        if pp: eurl = pp

        new_entries.append({
            "original_id": intel['id'], "date": date, "iso_date": iso,
            "title": ar.get('title', 'UPDATE').upper(), "type": etype,
            "desc": intel['clean'], "image": intel['img'], "url": eurl,
            "version": ar.get('version', '').upper()
        })

    output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": old_db + new_entries}
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)

if __name__ == "__main__":
    scrape()
