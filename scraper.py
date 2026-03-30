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
    return res.json() if res.status_code == 200 else[]

def find_deep_img(obj):
    if not obj: return ""
    if isinstance(obj, str):
        if any(ext in obj.lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']) and 'http' in obj:
            return obj
    if isinstance(obj, dict):
        for key in['url', 'proxy_url']:
            if key in obj and isinstance(obj[key], str) and any(ext in obj[key].lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                return obj[key]
        if 'image' in obj and isinstance(obj['image'], dict):
            res = find_deep_img(obj['image'])
            if res: return res
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
            for emb in msg.get('embeds',[]):
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
    Identify the correct event dates and short titles.
    
    CRITICAL DATE RULES:
    1. Read the CONTENT. If the text mentions a future date (e.g. "April 7th", "1st April"), convert it to YYYY-MM-DD (e.g. "2026-04-07", "2026-04-01") and use it.
    2. If the CONTENT does NOT mention a future date (e.g. it says "is LIVE!" or "Available now"), you MUST use the "POSTED" date provided.
    3. DO NOT group everything on today's date. Respect the text dates or POSTED dates.
    
    RULES:
    - If a single message announces multiple features on the same date, create ONE event for each feature.
    - JSON list only. Fields: "date" (YYYY-MM-DD), "title" (short), "original_id", "type" (patch/hero/season/twitch).
    
    Messages:
    {messages_text}
    """
    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.0 # Set to 0 to make it strictly logical, not creative
    )
    raw = chat.choices[0].message.content
    return json.loads(re.search(r'\[.*\]', raw, re.DOTALL).group(0))

def scrape():
    print("Starting Date-Accurate Scrape...")
    messages = get_discord_messages()
    if not messages: return

    intel_pool = {}
    ai_input_list =[]
    for m in messages:
        text = extract_full_content(m)
        img = find_deep_img(m)
        if text:
            intel_pool[m['id']] = {
                "text": clean_discord_text(text), 
                "img": img, 
                "url": f"https://discord.com/channels/1055546338907017278/{CHANNEL_ID}/{m['id']}"
            }
            # THE FIX: Injecting the actual post date back into the AI Prompt
            posted_date = m['timestamp'][:10]
            ai_input_list.append(f"ID: {m['id']} | POSTED: {posted_date} | CONTENT: {text}")

    try:
        ai_events = ask_groq("\n---\n".join(ai_input_list))
        
        try:
            with open('events.json', 'r') as f:
                old_data = json.load(f)
                master_list = old_data.get('events', [])
        except: master_list =[]

        for ae in ai_events:
            mid = ae.get('original_id')
            if mid in intel_pool:
                full_text = intel_pool[mid]['text'].lower()
                etype = ae['type']
                eurl = intel_pool[mid]['url']
                if any(x in full_text for x in["twitch", "stream"]):
                    etype, eurl = "twitch", "https://www.twitch.tv/predecessorgame"
                
                iso = ae.get('iso_date', ae['date'] + ("T18:00:00Z" if etype == "twitch" else "T00:00:00Z"))

                new_obj = {
                    "date": ae['date'], "iso_date": iso, "title": ae['title'].strip().upper(), "type": etype,
                    "desc": intel_pool[mid]['text'], "url": eurl, "image": intel_pool[mid]['img']
                }

                def normalize(t): return re.sub(r'[^A-Z0-9]', '', t.upper())
                
                found_match = False
                for i, existing in enumerate(master_list):
                    if existing['date'] == new_obj['date']:
                        n1, n2 = normalize(new_obj['title']), normalize(existing['title'])
                        if n1 in n2 or n2 in n1:
                            if len(new_obj['title']) >= len(existing['title']):
                                existing['title'] = new_obj['title']
                                if new_obj['image']: existing['image'] = new_obj['image']
                                existing['iso_date'] = new_obj['iso_date']
                            found_match = True
                            break
                if not found_match: master_list.append(new_obj)

        # Remove very old items
        master_list =[e for e in master_list if e.get('desc') and e['date'] >= "2026-02-01"]

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": master_list}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Success: {len(master_list)} events stored on correct dates.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
