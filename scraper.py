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
    print(f"--- DISCORD: Connecting to Channel {CHANNEL_ID} ---")
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=25"
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print(f"DISCORD ERROR: {res.status_code} - Check if Bot is in server and Token is correct.")
        return []
    msgs = res.json()
    print(f"DISCORD SUCCESS: Found {len(msgs)} messages.")
    return msgs

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

def clean_discord_text(text):
    text = re.sub(r'<@&?\d+>', '', text)
    text = text.replace('🔔', '')
    return re.sub(r'\n\s*\n', '\n', text).strip()

def extract_full_content(m):
    text = m.get('content', '')
    # Log what we see in regular content
    if text: print(f"Found Content: {text[:50]}...")
    
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
    print("--- AI: Consulting Llama-3 ---")
    client = Groq(api_key=GROQ_API_KEY)
    today = datetime.now().strftime("%A, %B %d, %Y")
    
    prompt = f"""
    Today is {today}. Context: Predecessor Game Discord.
    Extract every event, patch, or stream mentioned. 
    
    RULES:
    1. If the text mentions a specific date (April 7, etc), use it.
    2. Format dates as YYYY-MM-DD.
    3. Title must be short and matching the card label.
    4. Return ONLY a JSON list.
    
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
    except Exception as e:
        print(f"AI ERROR: {e}")
        return []

def scrape():
    messages = get_discord_messages()
    master_list = []
    
    if not messages:
        print("No messages to process. Ensure Bot is in the server.")
    
    intel_pool = {}
    ai_input_list = []
    for m in messages:
        text = extract_full_content(m)
        img = find_deep_img(m)
        if text:
            intel_pool[m['id']] = {
                "text": clean_discord_text(text),
                "img": img,
                "posted": m['timestamp'],
                "url": f"https://discord.com/channels/1055546338907017278/1487129767865225261/{m['id']}"
            }
            ai_input_list.append(f"ID: {m['id']} | CONTENT: {text}")

    if ai_input_list:
        ai_events = ask_groq("\n---\n".join(ai_input_list))
        for ae in ai_events:
            mid = ae.get('original_id')
            if mid in intel_pool:
                # Force format
                date_str = ae['date']
                if not re.search(r'\d{4}-\d{2}-\d{2}', date_str):
                    date_str = intel_pool[mid]['posted'][:10]
                
                etype = ae.get('type', 'news')
                eurl = "https://www.twitch.tv/predecessorgame" if etype == "twitch" else intel_pool[mid]['url']
                
                master_list.append({
                    "date": date_str,
                    "iso_date": date_str + ("T18:00:00Z" if etype == "twitch" else "T15:00:00Z"),
                    "title": ae['title'].upper(),
                    "type": etype,
                    "desc": intel_pool[mid]['text'],
                    "image": intel_pool[mid]['img'],
                    "url": eurl
                })

    output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": master_list}
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"SUCCESS: Saved {len(master_list)} events.")

if __name__ == "__main__":
    scrape()
