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

def extract_message_text(m):
    full_text = m.get('content', '')
    if 'message_snapshots' in m:
        for snapshot in m['message_snapshots']:
            snap_content = snapshot.get('message', {}).get('content', '')
            if snap_content: full_text += f"\n[FORWARDED]: {snap_content}"
    if 'embeds' in m:
        for embed in m['embeds']:
            full_text += f"\n[EMBED]: {embed.get('title', '')} {embed.get('description', '')}"
    return full_text.strip()

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_KEY)
    today = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    Today's Date: {today}. Context: "Predecessor" game announcements.
    Task: Extract event dates and descriptions.
    
    RULES:
    1. Output a JSON list only.
    2. "date": ACTUAL start date (YYYY-MM-DD).
    3. "title": Short punchy name (max 30 chars).
    4. "desc": A detailed summary of the announcement (max 300 chars). Keep the tone informative.
    5. "type": "patch" or "news".
    
    Messages:
    {messages_text}

    OUTPUT FORMAT:
    [
      {{"date": "YYYY-MM-DD", "title": "Name", "desc": "Full details...", "type": "patch/news", "url": "link", "image": "img"}}
    ]
    """
    
    chat_completion = client.chat.create(
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

    combined = ""
    for m in messages:
        text = extract_message_text(m)
        if text: combined += f"SENT: {m['timestamp']} | MSG: {text}\n---\n"

    try:
        events = ask_groq(combined)
        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": events}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"SUCCESS: {len(events)} detailed events saved.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
