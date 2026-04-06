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
    return res.json() if res.status_code == 200 else[]

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

def extract_all_content_and_links(m):
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
    clean_urls =[u.rstrip('.,!?"\')') for u in urls]
    return full_text, clean_urls

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_API_KEY)
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""
    Today is {today}. Context: "Predecessor" game announcements.
    TASK: Extract event dates and versions.
    
    RULES:
    1. If the message explicitly mentions a FUTURE START DATE (like "April 7th"), return it as YYYY-MM-DD.
    2. If the message says "Live Now", "Available Now", or does NOT mention a specific future date, you MUST set "date" to "None".
    3. Identify a VERSION NUMBER (e.g., V1.13) if mentioned.
    4. Return a short, uppercase TITLE.
    5. Return ONLY a JSON list of objects:[{{"idx": 0, "date": "YYYY-MM-DD or None", "version": "V1.xx or None", "title": "..."}}]
    
    Messages:
    {messages_text}
    """
    try:
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.0
        )
        raw = chat.choices[0].message.content
        return json.loads(re.search(r'\[.*\]', raw, re.DOTALL).group(0))
    except: return[]

def scrape():
    print("--- Starting Discord Timestamp Sync ---")
    messages = get_discord_messages()
    if not messages: return

    try:
        with open('events.json', 'r') as f:
            db = json.load(f).get('events',[])
    except: db = []

    existing_ids = [str(e.get('original_id')) for e in db]
    to_process =[]
    ai_input = ""
    
    for m in messages:
        if str(m['id']) in existing_ids: continue # Persistence Rule
        
        full_text, all_urls = extract_all_content_and_links(m)
        if full_text:
            to_process.append({
                "id": m['id'], "raw": full_text, "urls": all_urls,
                "clean": re.sub(r'<@&?\d+>', '', full_text).replace('🔔', '').strip(),
                "img": find_deep_img(m), 
                "posted": m['timestamp'][:10] # EXACT DISCORD CREATION DATE (YYYY-MM-DD)
            })
            ai_input += f"BLOCK_INDEX: {len(to_process)-1}\nCONTENT: {full_text}\n---\n"

    if not to_process:
        print("Persistence active. No new messages.")
        return

    ai_results = ask_groq(ai_input)
    new_entries =[]

    for ar in ai_results:
        idx = ar.get('idx')
        if idx is None or idx >= len(to_process): continue
        
        intel = to_process[idx]
        text_lower = intel['raw'].lower()
        
        # 1. DATE HIERARCHY
        event_date = str(ar.get('date')).strip()
        version = str(ar.get('version')).strip()
        
        # Nullify bad AI guesses
        if event_date.lower() == "none" or not re.match(r'^\d{4}-\d{2}-\d{2}$', event_date):
            event_date = None
        
        # Version Sync
        if not event_date and version and version.lower() != "none":
            for old in (db + new_entries):
                if version.lower() in old['title'].lower() or version.lower() in old.get('desc', '').lower():
                    event_date = old['date']
                    break
        
        # Final Fallback -> Discord Post Date
        if not event_date:
            event_date = intel['posted']

        # 2. CATEGORY & LINK ASSIGNMENT
        etype = "patch"
        eurl = "https://www.predecessorgame.com/en-US/news"
        
        yt_url = next((u for u in intel['urls'] if "youtube.com" in u or "youtu.be" in u), None)
        pp_url = next((u for u in intel['urls'] if "playp.red" in u), None)

        if "twitch" in text_lower or "live stream" in text_lower or "livestream" in text_lower:
            etype, eurl = "twitch", "https://www.twitch.tv/predecessorgame"
        elif yt_url:
            etype, eurl = "youtube", yt_url
        
        if pp_url: # playp.red priority override
            eurl = pp_url

        new_entries.append({
            "original_id": intel['id'],
            "date": event_date,
            "iso_date": event_date + ("T18:00:00Z" if etype == "twitch" else "T00:00:00Z"),
            "title": ar.get('title', 'UPDATE').upper(),
            "type": etype,
            "desc": intel['clean'],
            "image": intel['img'],
            "url": eurl
        })

    # Combine and Save
    final_list = db + new_entries
    output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": final_list}
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"Success: {len(new_entries)} new events added.")

if __name__ == "__main__":
    scrape()
