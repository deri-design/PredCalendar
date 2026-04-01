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
    print(f"Connecting to Discord channel {CHANNEL_ID}...")
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=25"
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print(f"DISCORD ERROR: {res.status_code} - {res.text}")
        return []
    messages = res.json()
    print(f"Found {len(messages)} messages.")
    return messages

def force_iso_date(date_str, posted_date):
    """Rigorous converter for dates like 'April 7' to '2026-04-07'"""
    try:
        # Clean suffixes (7th -> 7)
        clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', str(date_str), flags=re.I)
        # If no year is found (e.g. "April 7"), add 2026
        if not re.search(r'\d{4}', clean):
            clean += " 2026"
        
        # Match Month Day Year
        match = re.search(r'([a-zA-Z]+)\s+(\d+)\s+(\d{4})', clean)
        if match:
            mon, day, year = match.groups()
            dt = datetime.strptime(f"{mon[:3].capitalize()} {day} {year}", "%b %d %Y")
            return dt.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Date conversion failed for '{date_str}': {e}")
    
    return posted_date[:10] # Fallback to the day the message was sent

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
    print("Consulting Groq AI...")
    client = Groq(api_key=GROQ_API_KEY)
    today = datetime.now().strftime("%A, %B %d, %Y")
    
    prompt = f"""
    Today is {today}. Context: Predecessor Game Discord.
    TASK: Extract event dates (like patch releases or streams).
    
    RULES:
    - Return ONLY a JSON list.
    - Use "date": "YYYY-MM-DD" or "Month Day" format.
    - "original_id": Must match the ID provided.
    
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
    except Exception as e:
        print(f"AI ERROR: {e}")
        return []

def scrape():
    messages = get_discord_messages()
    master_list = []
    
    if messages:
        intel_pool = {}
        ai_input_list = []
        for m in messages:
            text = extract_full_content(m)
            if text:
                intel_pool[m['id']] = {
                    "text": re.sub(r'<@&?\d+>', '', text).replace('🔔', '').strip(),
                    "posted": m['timestamp'],
                    "id": m['id']
                }
                ai_input_list.append(f"ID: {m['id']} | CONTENT: {text}")

        ai_events = ask_groq("\n---\n".join(ai_input_list))
        
        for ae in ai_events:
            mid = ae.get('original_id')
            if mid in intel_pool:
                clean_d = force_iso_date(ae.get('date', ''), intel_pool[mid]['posted'])
                etype = ae.get('type', 'news')
                if "twitch" in intel_pool[mid]['text'].lower() or "stream" in intel_pool[mid]['text'].lower():
                    etype = "twitch"
                
                master_list.append({
                    "date": clean_d,
                    "iso_date": clean_d + ("T18:00:00Z" if etype == "twitch" else "T00:00:00Z"),
                    "title": ae.get('title', 'UPDATE').upper(),
                    "type": etype,
                    "desc": intel_pool[mid]['text'],
                    "url": "https://www.twitch.tv/predecessorgame" if etype == "twitch" else f"https://discord.com/channels/1055546338907017278/1487129767865225261/{mid}"
                })

    # CRITICAL: Always write the file, even if list is empty, to prevent git error
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "events": master_list
    }
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)
    
    print(f"Scrape finished. Saved {len(master_list)} events.")

if __name__ == "__main__":
    scrape()
