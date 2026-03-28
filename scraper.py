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
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=20"
    res = requests.get(url, headers=headers)
    return res.json() if res.status_code == 200 else []

def find_deep_img(obj):
    """Recursively crawls a JSON object to find the first URL ending in an image extension."""
    if isinstance(obj, str):
        if any(ext in obj.lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']):
            if 'http' in obj: return obj
    if isinstance(obj, dict):
        # Prioritize Discord's specific image fields
        if 'image' in obj and isinstance(obj['image'], dict):
            url = obj['image'].get('url')
            if url: return url
        for v in obj.values():
            res = find_deep_img(v)
            if res: return res
    if isinstance(obj, list):
        for i in obj:
            res = find_deep_img(i)
            if res: return res
    return ""

def extract_full_content(m):
    """Grabs standard content + forwarded content + embed content."""
    text = m.get('content', '')
    if 'message_snapshots' in m:
        for snap in m['message_snapshots']:
            msg = snap.get('message', {})
            text += f"\n{msg.get('content', '')}"
            for emb in msg.get('embeds', []):
                text += f"\n{emb.get('title', '')} {emb.get('description', '')}"
    if 'embeds' in m:
        for emb in m['embeds']:
            text += f"\n{emb.get('title', '')} {emb.get('description', '')}"
    return text.strip()

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_KEY)
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"Today is {today}. Context: 'Predecessor' game. Rules: JSON list only. date: YYYY-MM-DD. title: short. original_id: match to provided ID. type: patch/news. Messages: {messages_text}"
    
    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.1
    )
    raw = chat.choices[0].message.content
    return json.loads(re.search(r'\[.*\]', raw, re.DOTALL).group(0))

def scrape():
    messages = get_discord_messages()
    if not messages: return

    intel_pool = {}
    ai_input_list = []

    for m in messages:
        text = extract_full_content(m)
        img = find_deep_img(m) # NEW: Deep search for image
        if text:
            intel_pool[m['id']] = {
                "text": text, "img": img, 
                "url": f"https://discord.com/channels/1055546338907017278/{CHANNEL_ID}/{m['id']}"
            }
            ai_input_list.append(f"ID: {m['id']} | CONTENT: {text}")

    try:
        ai_events = ask_groq("\n---\n".join(ai_input_list))
        final = []
        for ae in ai_events:
            mid = ae.get('original_id')
            if mid in intel_pool:
                final.append({
                    "date": ae['date'], "title": ae['title'], "type": ae['type'],
                    "desc": intel_pool[mid]['text'], "url": intel_pool[mid]['url'], "image": intel_pool[mid]['img']
                })

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": final}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
