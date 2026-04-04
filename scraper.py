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
    if isinstance(obj, list):
        for i in obj:
            res = find_deep_img(i)
            if res: return res
    return ""

def extract_all_text_and_links(m):
    text_segments = [m.get('content', '')]
    urls = re.findall(r'(https?://[^\s]+)', m.get('content', ''))
    def process_obj(obj):
        if 'message_snapshots' in obj:
            for snap in obj['message_snapshots']:
                snap_msg = snap.get('message', {})
                text_segments.append(snap_msg.get('content', ''))
                urls.extend(re.findall(r'(https?://[^\s]+)', snap_msg.get('content', '')))
                process_obj(snap_msg)
        if 'embeds' in obj:
            for emb in obj['embeds']:
                text_segments.append(emb.get('title', ''))
                text_segments.append(emb.get('description', ''))
                if emb.get('url'): urls.append(emb['url'])
    process_obj(m)
    full_text = "\n".join(filter(None, text_segments))
    return full_text, [u.rstrip('.,!?"\')') for u in urls]

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_API_KEY)
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""
    Today is {today}. Context: "Predecessor" game announcements.
    TASK: Identify specific titles, release dates, and version numbers.
    
    RULES:
    1. For EACH message block, identify a specific START DATE (YYYY-MM-DD) if mentioned.
    2. Identify the VERSION NUMBER (e.g., V1.13) mentioned in the content.
    3. Extract the SPECIFIC TITLE of the news (e.g. "V1.13 Reveals Round-Up" or "Adele Hero Trailer"). Do not use generic words like "UPDATE".
    4. "original_id": Use the EXACT numeric ID provided in the block header.
    
    Messages:
    {messages_text}
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
    print("--- Starting Advanced Hierarchy Scrape ---")
    messages = get_discord_messages()
    if not messages: return

    try:
        with open('events.json', 'r') as f:
            db_data = json.load(f)
            master_events = db_data.get('events', [])
    except: master_events = []

    # Build Map for Version Syncing
    ver_date_map = {}
    for e in master_events:
        v_match = re.search(r'V\d+\.\d+', e['title'] + e['desc'], re.I)
        if v_match: ver_date_map[v_match.group(0).upper()] = e['date']

    existing_ids = [str(e.get('original_id')) for e in master_events]
    intel_pool = {}
    ai_input_list = []
    
    for m in messages:
        if str(m['id']) in existing_ids: continue # Persistence Rule
        full_text, all_urls = extract_all_text_and_links(m)
        if full_text:
            intel_pool[str(m['id'])] = {
                "raw": full_text,
                "clean": re.sub(r'<@&?\d+>', '', full_text).replace('🔔', '').strip(),
                "all_urls": all_urls,
                "img": find_deep_img(m),
                "posted": m['timestamp'][:10]
            }
            ai_input_list.append(f"BLOCK_ID: {m['id']}\nCONTENT: {full_text}")

    if not ai_input_list:
        print("No new events.")
        return

    ai_results = ask_groq("\n---\n".join(ai_input_list))
    new_entries = []

    for ar in ai_results:
        mid = str(ar.get('original_id') or ar.get('BLOCK_ID'))
        if mid not in intel_pool: continue
        
        intel = intel_pool[mid]
        text_lower = intel['raw'].lower()
        urls = intel['all_urls']
        
        # 1. DATE HIERARCHY
        event_date = ar.get('date') # Direct Mention
        version = ar.get('version')
        
        if (not event_date or event_date == "None") and version: # Version Sync
            event_date = ver_date_map.get(version.upper())
        
        if not event_date or event_date == "None": # Fallback
            event_date = intel['posted']

        if version and event_date: ver_date_map[version.upper()] = event_date

        # 2. CATEGORY & LINK HIERARCHY
        etype, eurl = "patch", "https://www.predecessorgame.com/en-US/news"
        yt_url = next((u for u in urls if "youtube.com" in u or "youtu.be" in u), None)
        pp_url = next((u for u in urls if "playp.red" in u), None)

        if any(x in text_lower for x in ["twitch", "live stream"]):
            etype, eurl = "twitch", "https://www.twitch.tv/predecessorgame"
        elif yt_url:
            etype, eurl = "youtube", yt_url
        
        if pp_url: eurl = pp_url # playp.red priority 3.0

        new_entries.append({
            "original_id": mid, "date": event_date,
            "iso_date": event_date + ("T18:00:00Z" if etype == "twitch" else "T15:00:00Z"),
            "title": ar.get('title', 'UPDATE').upper(), "type": etype,
            "desc": intel['clean'], "image": intel['img'], "url": eurl
        })

    output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": master_events + new_entries}
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"Sync complete. Added {len(new_entries)} items.")

if __name__ == "__main__":
    scrape()
