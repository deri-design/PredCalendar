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
    Today is {today}. Context: "Predecessor" game announcements.
    TASK: Extract event data. 
    
    RULES:
    1. For EACH block, identify a specific START DATE (YYYY-MM-DD) if mentioned.
    2. Identify any VERSION NUMBER (e.g., V1.13) mentioned.
    3. Return ONLY a JSON list of objects.
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
    print("--- Starting Revised Logic Scrape ---")
    messages = get_discord_messages()
    if not messages: return

    try:
        with open('events.json', 'r') as f:
            old_db = json.load(f).get('events', [])
    except: old_db = []

    existing_ids = [str(e.get('original_id')) for e in old_db]
    intel_pool = {}
    ai_input_list = []
    
    for m in messages:
        if str(m['id']) in existing_ids: continue # Persistence Rule
        
        content = extract_full_content(m)
        if content:
            intel_pool[m['id']] = {
                "raw": content,
                "clean": re.sub(r'<@&?\d+>', '', content).replace('🔔', '').strip(),
                "img": find_deep_img(m),
                "posted": m['timestamp'][:10]
            }
            ai_input_list.append(f"BLOCK_ID: {m['id']}\nCONTENT: {content}")

    if not ai_input_list:
        print("No new events to add. Persistence active.")
        return

    ai_results = ask_groq("\n---\n".join(ai_input_list))
    new_entries = []

    for ar in ai_results:
        mid = ar.get('original_id') or ar.get('BLOCK_ID')
        if not mid or str(mid) not in intel_pool: continue
        
        intel = intel_pool[str(mid)]
        full_text = intel['raw']
        
        # 1. Date Hierarchy: Direct -> Version Sync -> Posted
        event_date = ar.get('date')
        version = ar.get('version')
        
        if (not event_date or event_date == "None") and version:
            # Search DB for this version
            for old in (old_db + new_entries):
                if version.lower() in old['title'].lower() or version.lower() in old['desc'].lower():
                    event_date = old['date']
                    break
        
        if not event_date or event_date == "None":
            event_date = intel['posted']

        # 2. Category & Link Assignment
        etype = "patch" # Default
        eurl = "https://www.predecessorgame.com/en-US/news"
        
        yt_match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s]+)', full_text)
        pp_match = re.search(r'(https://playp\.red/[^\s]+)', full_text)

        if any(x in full_text.lower() for x in ["twitch", "live stream"]):
            etype, eurl = "twitch", "https://www.twitch.tv/predecessorgame"
        elif yt_match:
            etype, eurl = "youtube", yt_match.group(0).rstrip('.,!?"\')')
        
        if pp_match: # playp.red priority
            eurl = pp_match.group(0).rstrip('.,!?"\')')

        new_entries.append({
            "original_id": mid,
            "date": event_date,
            "iso_date": event_date + ("T18:00:00Z" if etype == "twitch" else "T00:00:00Z"),
            "title": ar.get('title', 'UPDATE').upper(),
            "type": etype,
            "desc": intel['clean'],
            "image": intel['img'],
            "url": eurl
        })

    # Combine and Save
    final_list = old_db + new_entries
    output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": final_list}
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"Success: {len(new_entries)} new events added.")

if __name__ == "__main__":
    scrape()
