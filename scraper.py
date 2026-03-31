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
    return res.json() if res.status_code == 200 else []

def force_iso_date(date_str):
    """Ensures dates are YYYY-MM-DD even if AI fails."""
    try:
        # Standardize month names for parsing
        date_str = date_str.replace("th", "").replace("st", "").replace("nd", "").replace("rd", "")
        # Try to parse 'April 7 2026'
        if not re.search(r'\d{4}', date_str):
            date_str += f" {datetime.now().year}"
        
        # Using a more flexible regex-based parser
        match = re.search(r'([a-zA-Z]+)\s+(\d+)\s+(\d{4})', date_str)
        if match:
            mon, day, year = match.groups()
            dt = datetime.strptime(f"{mon[:3].capitalize()} {day} {year}", "%b %d %Y")
            return dt.strftime("%Y-%m-%d")
    except:
        pass
    return date_str # Return original if parsing fails

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
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()

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
    client = Groq(api_key=GROQ_KEY)
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""
    Today is {today}. Context: "Predecessor" game announcements.
    Identify ACTUAL release/event dates and short titles. 
    RULES: 
    1. DATE MUST BE FORMATTED AS YYYY-MM-DD. Example: 2026-04-07.
    2. Format: JSON list only.
    Messages: {messages_text}
    """
    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.1
    )
    raw = chat.choices[0].message.content
    return json.loads(re.search(r'\[.*\]', raw, re.DOTALL).group(0))

def scrape():
    print("Executing Date-Validation Scrape...")
    messages = get_discord_messages()
    if not messages: return
    intel_pool = {}
    ai_input_list = []
    for m in messages:
        text = extract_full_content(m)
        img = find_deep_img(m)
        if text:
            intel_pool[m['id']] = {"text": clean_discord_text(text), "img": img, "url": f"https://discord.com/channels/1055546338907017278/1487129767865225261/{m['id']}"}
            ai_input_list.append(f"ID: {m['id']} | CONTENT: {text}")

    try:
        ai_events = ask_groq("\n---\n".join(ai_input_list))
        master_list = []
        for ae in ai_events:
            mid = ae.get('original_id')
            if mid in intel_pool:
                # FORCE CORRECT DATE FORMAT
                clean_date = force_iso_date(ae['date'])
                
                full_text = intel_pool[mid]['text'].lower()
                etype = ae.get('type', 'news')
                if any(x in full_text for x in ["twitch", "stream"]): etype = "twitch"
                
                eurl = "https://www.twitch.tv/predecessorgame" if etype == "twitch" else intel_pool[mid]['url']
                iso = clean_date + ("T18:00:00Z" if etype == "twitch" else "T00:00:00Z")

                master_list.append({
                    "date": clean_date, "iso_date": iso, "title": ae['title'].upper(), "type": etype,
                    "desc": intel_pool[mid]['text'], "url": eurl, "image": intel_pool[mid]['img']
                })

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": master_list}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print("Scrape and Formatting Complete.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
