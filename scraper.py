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
    if res.status_code != 200:
        return []
    return res.json()

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

def find_external_link(m, full_text):
    """Prioritizes YouTube and playp.red links. Rejects Discord internal links."""
    # 1. Gather all potential URLs from text and embeds
    urls = re.findall(r'(https?://[^\s]+)', full_text)
    for emb in m.get('embeds', []):
        if emb.get('url'): urls.append(emb['url'])
    
    # Clean the URLs
    cleaned_urls = []
    for u in urls:
        u = u.rstrip('.,!?"\')')
        # Skip internal Discord links
        if "discord.com/channels" in u: continue
        # Skip direct image links
        if any(u.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']): continue
        cleaned_urls.append(u)

    # 2. Priority Logic
    # 1st Priority: YouTube
    for u in cleaned_urls:
        if "youtube.com" in u or "youtu.be" in u: return u
    # 2nd Priority: playp.red
    for u in cleaned_urls:
        if "playp.red" in u: return u
    
    # 3rd Priority: Any other external link found
    if cleaned_urls: return cleaned_urls[0]
    
    # Final Fallback
    return "https://www.predecessorgame.com/en-US/news"

def clean_discord_text(text):
    text = re.sub(r'<@&?\d+>', '', text)
    text = text.replace('🔔', '')
    return re.sub(r'\n\s*\n', '\n', text).strip()

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
    prompt = f"Today is {today}. Extract game events from Discord. Return ONLY a JSON list: date: YYYY-MM-DD, title: short name, original_id: msg id, type: patch/hero/season/twitch. Messages: {messages_text}"
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
    if not messages: return
    intel_pool = {}
    ai_input_list = []
    for m in messages:
        text = extract_full_content(m)
        img = find_deep_img(m)
        ext_link = find_external_link(m, text)
        if text:
            intel_pool[m['id']] = {
                "text": clean_discord_text(text),
                "img": img,
                "posted": m['timestamp'],
                "url": ext_link
            }
            ai_input_list.append(f"ID: {m['id']} | CONTENT: {text}")

    try:
        ai_events = ask_groq("\n---\n".join(ai_input_list))
        master_list = []
        for ae in ai_events:
            if not isinstance(ae, dict): continue
            mid = ae.get('original_id')
            if mid in intel_pool:
                date = ae.get('date', intel_pool[mid]['posted'][:10])
                title = ae.get('title', 'UPDATE').upper()
                etype = "patch" if "patch" in title.lower() else "news"
                if "twitch" in intel_pool[mid]['text'].lower() or "stream" in intel_pool[mid]['text'].lower(): etype = "twitch"
                
                # Link Logic
                eurl = intel_pool[mid]['url']
                if etype == "twitch": eurl = "https://www.twitch.tv/predecessorgame"
                
                iso = date + ("T18:00:00Z" if etype == "twitch" else "T15:00:00Z")

                master_list.append({
                    "date": date, "iso_date": iso, "title": title, "type": etype,
                    "desc": intel_pool[mid]['text'], "image": intel_pool[mid]['img'], "url": eurl,
                    "original_id": mid
                })

        # Deduplication: Merge items on the same day with similar titles
        unique_map = {}
        for e in sorted(master_list, key=lambda x: len(x['title']), reverse=True):
            fingerprint = f"{e['date']}_{e['original_id']}"
            if fingerprint not in unique_map: unique_map[fingerprint] = e

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": list(unique_map.values())}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
