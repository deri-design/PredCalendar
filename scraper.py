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
    TASK: Process Discord blocks into structured JSON.
    
    RULES:
    1. Identify a SPECIFIC START DATE (YYYY-MM-DD) if mentioned in CONTENT.
    2. Identify a VERSION NUMBER (e.g. V1.13) if mentioned in CONTENT.
    3. Extract a short, punchy TITLE.
    4. "original_id": Return the numeric ID provided in the block header.
    
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
    print("--- Executing Hierarchical Logic Sync ---")
    messages = get_discord_messages()
    if not messages: return

    try:
        with open('events.json', 'r') as f:
            db_data = json.load(f)
            master_events = db_data.get('events', [])
    except:
        master_events = []

    existing_ids = [str(e.get('original_id')) for e in master_events]
    intel_pool = {}
    ai_input_list = []
    
    for m in messages:
        # Persistence Rule: If present in DB, do not modify or move.
        if str(m['id']) in existing_ids: continue
        
        content = extract_full_content(m)
        if content:
            intel_pool[str(m['id'])] = {
                "raw": content,
                "clean": re.sub(r'<@&?\d+>', '', content).replace('🔔', '').strip(),
                "img": find_deep_img(m),
                "posted": m['timestamp'][:10]
            }
            ai_input_list.append(f"BLOCK_ID: {m['id']}\nCONTENT: {content}")

    if not ai_input_list:
        print("Persistence active. No new messages.")
        return

    ai_results = ask_groq("\n---\n".join(ai_input_list))
    new_entries = []

    for ar in ai_results:
        mid = str(ar.get('original_id') or ar.get('BLOCK_ID'))
        if mid not in intel_pool: continue
        
        intel = intel_pool[mid]
        text_lower = intel['raw'].lower()
        
        # --- DATE DETERMINATION HIERARCHY ---
        # 1. Direct Mention
        event_date = ar.get('date')
        
        # 2. Version Sync
        ver = ar.get('version')
        if (not event_date or event_date == "None") and ver:
            # Search entire DB (including other new entries) for this version
            for item in (master_events + new_entries):
                if ver.lower() in item['title'].lower() or ver.lower() in item['desc'].lower():
                    event_date = item['date']
                    break
        
        # 3. Creation Date Fallback
        if not event_date or event_date == "None":
            event_date = intel['posted']

        # --- CATEGORY & LINK ASSIGNMENT ---
        etype = "patch" 
        eurl = "https://www.predecessorgame.com/en-US/news"
        
        # Link Detection
        urls = re.findall(r'(https?://[^\s]+)', intel['raw'])
        yt_url = next((u for u in urls if "youtube.com" in u or "youtu.be" in u), None)
        pp_url = next((u for u in urls if "playp.red" in u), None)

        if any(x in text_lower for x in ["twitch", "live stream"]):
            etype, eurl = "twitch", "https://www.twitch.tv/predecessorgame"
        elif yt_url:
            etype, eurl = "youtube", yt_url.rstrip('.,!?"\')')
        
        # Special playp.red handling (Priority 3.0)
        if pp_url:
            eurl = pp_url.rstrip('.,!?"\')')

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

    # Rule: Persistence - Add new to existing
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "events": master_events + new_entries
    }
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"Success. Added {len(new_entries)} items.")

if __name__ == "__main__":
    scrape()
