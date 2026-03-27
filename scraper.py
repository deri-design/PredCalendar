import os
import requests
import json
import re
from google import genai
from datetime import datetime

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "1487129767865225261" 

def scrape():
    print("--- DEBUG: Starting AI Scrape ---")
    
    # 1. Fetch Discord
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=10"
    
    print(f"Connecting to Discord channel {CHANNEL_ID}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"DISCORD ERROR: {response.status_code} - {response.text}")
        return

    messages = response.json()
    print(f"SUCCESS: Found {len(messages)} messages in Discord.")

    combined_text = ""
    for m in messages:
        # Log the first 20 characters of each message to the console so we can see them
        print(f"Reading message: {m['content'][:30]}...")
        combined_text += f"SENT: {m['timestamp']} | MSG: {m['content']}\n---\n"

    # 2. Consult Gemini
    print("Sending text to Gemini 1.5-Flash...")
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        today = datetime.now().strftime("%A, %B %d, %Y")
        
        prompt = f"Today is {today}. Extract game events from these Discord messages into a JSON list with 'date' (YYYY-MM-DD), 'title', 'type' (patch/news), 'url', and 'image' fields. Messages: {combined_text}"
        
        response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        
        # Extract JSON list
        raw_text = response.text
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        events = json.loads(json_match.group(0)) if json_match else []

        # 3. Write File
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "events": events
        }
        
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        
        print(f"DONE: Written {len(events)} events to events.json")

    except Exception as e:
        print(f"AI ERROR: {e}")
        # Write an empty structure so Git doesn't fail
        with open('events.json', 'w') as f:
            json.dump({"last_updated": "Error", "events": []}, f)

if __name__ == "__main__":
    scrape()
