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

def find_best_image(msg_obj):
    """Deep searches a message object for any valid image URL."""
    if not msg_obj: return ""
    
    # 1. Check Attachments
    for att in msg_obj.get('attachments', []):
        url = att.get('url', '')
        if any(ext in url.lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']):
            return url
            
    # 2. Check Embeds (Image or Thumbnail)
    for emb in msg_obj.get('embeds', []):
        # Prefer the large 'image', fallback to 'thumbnail'
        img = emb.get('image') or emb.get('thumbnail')
        if img and img.get('url'):
            return img.get('url')
            
    return ""

def extract_intel(m):
    """Gathers 1:1 text and searches all layers for images."""
    raw_text = m.get('content', '')
    found_img = find_best_image(m)

    # Handle Forwarded Snapshots (This is where your patch note image lives)
    if 'message_snapshots' in m:
        for snapshot in m['message_snapshots']:
            snap_msg = snapshot.get('message', {})
            snap_content = snap_msg.get('content', '')
            if snap_content: 
                raw_text += f"\n{snap_content}"
            
            # If we haven't found an image yet, look inside the snapshot
            if not found_img:
                found_img = find_best_image(snap_msg)

    # Append all embed descriptions (like the text inside the Patch Notes box)
    if 'embeds' in m:
        for embed in m['embeds']:
            desc = embed.get('description', '')
            title = embed.get('title', '')
            if title or desc:
                raw_text += f"\n{title}\n{desc}"

    return raw_text.strip(), found_img

def ask_groq(messages_text):
    client = Groq(api_key=GROQ_KEY)
    today = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    Today is {today}. Context: "Predecessor" game announcements.
    TASK: Identify release dates and titles from the messages provided.
    
    RULES:
    1. Output JSON list ONLY.
    2. "date": The actual release/event date mentioned (YYYY-MM-DD).
    3. "title": A short title for the calendar (max 20 chars).
    4. "original_msg_id": Match this exactly to the ID provided.
    5. "type": "patch" if it's a version update, else "news".
    
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
    print("Initializing Visual Intel Scrape...")
    messages = get_discord_messages()
    if not messages: return

    intel_pool = {}
    ai_input_list = []

    for m in messages:
        text, img = extract_intel(m)
        if text:
            # Save the 1:1 raw data
            intel_pool[m['id']] = {
                "text": text, 
                "img": img, 
                "url": f"https://discord.com/channels/1055546338907017278/{CHANNEL_ID}/{m['id']}"
            }
            ai_input_list.append(f"ID: {m['id']} | SENT: {m['timestamp']} | CONTENT: {text}")

    ai_input_text = "\n---\n".join(ai_input_list)

    try:
        ai_events = ask_groq(ai_input_text)
        final_events = []
        
        for ae in ai_events:
            msg_id = ae.get('original_msg_id')
            if msg_id in intel_pool:
                final_events.append({
                    "date": ae['date'],
                    "title": ae['title'],
                    "desc": intel_pool[msg_id]['text'], 
                    "type": ae['type'],
                    "url": intel_pool[msg_id]['url'],
                    "image": intel_pool[msg_id]['img'] # This now contains the deep-scraped URL
                })

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "events": final_events}
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"SUCCESS: Synced {len(final_events)} events with high-res images.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
