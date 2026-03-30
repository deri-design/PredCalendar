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
        for key in ['url', 'proxy_url']:
            if key in obj and isinstance(obj[key], str) and any(ext in obj[key].lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                return obj[key]
        if 'image' in obj and isinstance(obj['image'], dict):
            res = find_deep_img(obj['image'])
            if res: return res
        if 'thumbnail' in obj and isinstance(obj['thumbnail'], dict):
            res = find_deep_img(obj['thumbnail'])
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

def extract_external_link(text, embeds):
    """Finds YouTube, website, or other external links, avoiding private Discord links."""
    # 1. Search raw text for http links
    urls = re.findall(r'(https?://[^\s]+)', text)
    for url in urls:
        url = url.rstrip('.,!?"\')')
        # Skip image file links (we just want web pages or videos)
        if any(url.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
            continue
        # CRITICAL: Skip private discord channel links
        if 'discord.com/channels' in url:
            continue
        return url
        
    # 2. Check embed objects (like YouTube video embeds)
    for emb in embeds:
        if 'url' in emb and 'discord.com/channels' not in emb['url']:
            return emb['url']
            
    # 3. Fallback to Official Website News Page (No broken links)
    return "https://www.predecessorgame.com/en-US/news"

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_KEY)
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    Today is {today}. Context: "Predecessor" game announcements.
    Identify the correct event dates and short titles.
    
    CRITICAL DATE RULES:
    1. Read the CONTENT. If the text mentions a future date (e.g. "April 7th", "1st April"), convert it to YYYY-MM-DD and use it.
    2. If the CONTENT does NOT mention a future date, you MUST use the "POSTED" date.
    
    Format: JSON list only. date: YYYY-MM-DD. title: short. original_id: match to ID. type: patch/hero/season/twitch.
    Messages: {messages_text}
    """
    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.0
    )
    raw = chat.choices[0].message.content
    return json.loads(re.search(r'\[.*\]', raw, re.DOTALL).group(0))

def scrape():
    print("Starting Scrape with External Link Tracking...")
    messages = get_discord_messages()
    if not messages: return

    intel_pool = {}
    ai_input_list =[]
    for m in messages:
        text = extract_full_content(m)
        img = find_deep_img(m)
        
        # Combine all embeds to search for external video/article URLs
        all_embeds = m.get('embeds',[])
        if 'message_snapshots' in m:
            for snap in m['message_snapshots']:
                all_embeds.extend(snap.get('message', {}).get('embeds',[]))
                
        # Extract the correct external link
        ext_url = extract_external_link(text, all_embeds)
        
        if text:
            intel_pool[m['id']] = {
                "text": clean_discord_text(text), 
                "img": img, 
                "url": ext_url
            }
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
                
                # --- TWITCH OVERRIDE (Untouched) ---
                if any(x in full_text for x in ["twitch", "stream"]):
                    etype = "twitch"
                    eurl = "https://www.twitch.tv/predecessorgame"
                
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
                                existing['url'] = new_obj['url']
                            found_match = True
                            break
                if not found_match: master_list.append(new_obj)

        master_list =[e for e in master_list if e.get('desc') and e['date'] >= "2026-02-01"]

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": master_list}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Success: {len(master_list)} events stored.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
