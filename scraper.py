import os
import requests
import json
import re
from datetime import datetime

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "1487129767865225261" 

def get_discord_messages():
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=15"
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print(f"DISCORD ERROR: {res.status_code}")
        return []
    return res.json()

def ask_gemini(messages_text):
    # Updated to use gemini-2.0-flash which was found in your available models list
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""
    Today's Date: {today}
    You are an AI data extractor for the game "Predecessor".
    
    Read these Discord announcements:
    ---
    {messages_text}
    ---
    
    TASK:
    Extract upcoming event dates, patches, or hero releases.
    Rules:
    1. Identify the ACTUAL date the event starts.
    2. Format as a strict JSON list only.
    3. Include fields: "date" (YYYY-MM-DD), "title", "type" (patch/news), "url", "image".
    4. If a message contains a link to an image or an article, put it in "image" or "url".
    
    OUTPUT ONLY THE JSON:
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }
    
    response = requests.post(api_url, json=payload)
    
    if response.status_code != 200:
        print(f"AI API ERROR: {response.status_code} - {response.text}")
        return None

    try:
        data = response.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        # The response_mime_type: application/json ensures Gemini returns clean JSON
        return json.loads(raw_text)
    except Exception as e:
        print(f"Parsing error: {e}")
        return None

def scrape():
    print("--- AI Agent: Logic Sync Start ---")
    
    # 1. Fetch Discord
    messages = get_discord_messages()
    if not messages:
        print("No messages found.")
        return

    combined = ""
    for m in messages:
        combined += f"SENT: {m['timestamp']} | CONTENT: {m['content']}\n---\n"

    # 2. Extract with Gemini 2.0
    print("Requesting extraction from Gemini 2.0-Flash...")
    events = ask_gemini(combined)
    
    if events is not None:
        # Sort events by date
        events.sort(key=lambda x: x.get('date', ''))
        
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "events": events
        }
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"SUCCESS: {len(events)} events written to events.json")
    else:
        print("Scrape failed to generate events.")

if __name__ == "__main__":
    scrape()
