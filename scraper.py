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

def python_date_finder(text):
    text = text.lower()
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    match = re.search(r'(\d{1,2})?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{1,2})?', text)
    if match:
        m_str, d_str = match.group(2), match.group(1) or match.group(3)
        if d_str:
            try:
                dt = datetime.strptime(f"{m_str.capitalize()} {d_str} 2026", "%b %d %Y")
                return dt.strftime("%Y-%m-%d")
            except: pass
    return None

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_API_KEY)
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""
    Today is {today}. Context: "Predecessor" game announcements.
    TASK: Extract events.
    RULES:
    1. Identify a SPECIFIC START DATE (YYYY-MM-DD) if mentioned in CONTENT.
    2. Identify a VERSION NUMBER (e.g., V1.13) if mentioned.
    3. Return ONLY a JSON list of objects.
    4. "original_id": Use the EXACT ID provided in the BLOCK_ID line.
    Messages: {messages_text}
    """
    try:
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.0
        )
        raw = chat.choices[0].message.content
        return json.loads(re.search(r'\[.*\]', raw, re.DOTALL).group(0))
    except: return []

def scrape():
    messages = get_discord_messages()
    if not messages: return

    try:
        with open('events.json', 'r') as f:
            db_data = json.load(f)
            master_events = db_data.get('events', [])
    except:
        master_events = []

    # Build a Version Map from existing data to power "Version Sync"
    version_date_map = {}
    for e in master_events:
        ver_match = re.search(r'V\d+\.\d+', e['title'] + e['desc'], re.I)
        if ver_match:
            version_date_map[ver_match.group(0).upper()] = e['date']

    existing_ids = [str(e.get('original_id')) for e in master_events]
    to_process, ai_input = [], ""
    
    for m in messages:
        if str(m['id']) in existing_ids: continue # Persistence Rule
        content = extract_full_content(m)
        if content:
            to_process.append({
                "id": m['id'], "raw": content, "img": find_deep_img(m), "posted": m['timestamp'][:10]
            })
            ai_input += f"BLOCK_ID: {m['id']}\nCONTENT: {content}\n---\n"

    if not to_process: return

    ai_results = ask_groq(ai_input)
    new_entries = []

    for ar in ai_results:
        mid = str(ar.get('original_id'))
        intel = next((x for x in to_process if str(x['id']) == mid), None)
        if not intel: continue
        
        # --- DATE DETERMINATION HIERARCHY ---
        # 1. Direct Mention
        event_date = ar.get('date') or python_date_finder(intel['raw'])
        
        # 2. Version Sync
        ver_match = re.search(r'V\d+\.\d+', ar.get('title', '') + intel['raw'], re.I)
        version = ver_match.group(0).upper() if ver_match else None
        
        if (not event_date or event_date == "None") and version:
            event_date = version_date_map.get(version)
        
        # 3. Creation Date Fallback
        if not event_date or event_date == "None":
            event_date = intel['posted']

        # Update map for other items in same run
        if version and event_date:
            version_date_map[version] = event_date

        # --- LINK ASSIGNMENT ---
        text_lower = intel['raw'].lower()
        etype, eurl = "patch", "https://www.predecessorgame.com/en-US/news"
        urls = re.findall(r'(https?://[^\s]+)', intel['raw'])
        yt_url = next((u for u in urls if "youtube.com" in u or "youtu.be" in u), None)
        pp_url = next((u for u in urls if "playp.red" in u), None)

        if "twitch" in text_lower or "live stream" in text_lower:
            etype, eurl = "twitch", "https://www.twitch.tv/predecessorgame"
        elif yt_url:
            etype, eurl = "youtube", yt_url.rstrip('.,!?"\')')
        
        if pp_url: eurl = pp_url.rstrip('.,!?"\')')

        new_entries.append({
            "original_id": mid, "date": event_date,
            "iso_date": event_date + ("T18:00:00Z" if etype == "twitch" else "T15:00:00Z"),
            "title": ar.get('title', 'UPDATE').upper(), "type": etype,
            "desc": re.sub(r'<@&?\d+>', '', intel['raw']).replace('🔔', '').strip(),
            "image": intel['img'], "url": eurl
        })

    output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": master_events + new_entries}
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)

if __name__ == "__main__":
    scrape()
