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

def extract_intel(m):
    """Gathers the EXACT raw text and images from Discord."""
    raw_text = m.get('content', '')
    img = ""
    
    def find_img(msg_obj):
        for att in msg_obj.get('attachments', []):
            if any(ext in att.get('url', '').lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                return att.get('url')
        for emb in msg_obj.get('embeds', []):
            if 'image' in emb: return emb['image'].get('url')
        return ""

    img = find_img(m)

    # Append forwarded text exactly
    if 'message_snapshots' in m:
        for snapshot in m['message_snapshots']:
            snap_msg = snapshot.get('message', {})
            snap_content = snap_msg.get('content', '')
            if snap_content: raw_text += f"\n{snap_content}"
            if not img: img = find_img(snap_msg)

    # Append embed descriptions exactly (where the "Daybreak V3" list often lives)
    if 'embeds' in m:
        for embed in m['embeds']:
            desc = embed.get('description', '')
            if desc: raw_text += f"\n{desc}"

    return raw_text.strip(), img

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_KEY)
    today = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    Today is {today}. Context: "Predecessor" game announcements.
    TASK: Identify the event dates.
    
    RULES:
    1. Output a JSON list only.
    2. "date": The release/event date (YYYY-MM-DD).
    3. "title": A very short title (max 25 chars).
    4. "original_msg_id": Match this to the ID provided in the text.
    5. "type": "patch" or "news".
    
    Messages:
    {messages_text}

    OUTPUT FORMAT:
    [
      {{"date": "YYYY-MM-DD", "title": "Name", "original_msg_id": "id", "type": "patch/news"}}
    ]
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.1
    )
    
    raw_text = chat_completion.choices[0].message.content
    json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    return json.loads(json_match.group(0)) if json_match else []

def scrape():
    messages = get_discord_messages()
    if not messages: return

    intel_pool = {}
    ai_input_list = []

    for m in messages:
        text, img = extract_intel(m)
        if text:
            # Store the 1:1 raw text indexed by message ID
            intel_pool[m['id']] = {"text": text, "img": img, "url": f"https://discord.com/channels/1055546338907017278/{CHANNEL_ID}/{m['id']}"}
            ai_input_list.append(f"ID: {m['id']} | SENT: {m['timestamp']} | CONTENT: {text}")

    ai_input_text = "\n---\n".join(ai_input_list)

    try:
        # AI only identifies the Date and Title
        ai_events = ask_groq(ai_input_text)
        
        final_events = []
        for ae in ai_events:
            msg_id = ae.get('original_msg_id')
            if msg_id in intel_pool:
                # We inject the 1:1 raw text here, bypassing AI alteration
                final_events.append({
                    "date": ae['date'],
                    "title": ae['title'],
                    "desc": intel_pool[msg_id]['text'], 
                    "type": ae['type'],
                    "url": intel_pool[msg_id]['url'],
                    "image": intel_pool[msg_id]['img']
                })

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": final_events}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"SUCCESS: Synced {len(final_events)} events 1:1 from Discord.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
