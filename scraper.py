import os
import requests
import json
import re
import google.generativeai as genai
from datetime import datetime

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "1487129767865225261" 

def scrape():
    print("--- AI Agent: Stable Sync Start ---")
    
    # 1. Fetch Discord
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=10"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"DISCORD ERROR: {response.status_code}")
        return

    messages = response.json()
    print(f"Read {len(messages)} messages from Discord.")

    combined_text = ""
    for m in messages:
        combined_text += f"SENT: {m['timestamp']} | MSG: {m['content']}\n---\n"

    # 2. Consult Gemini (Stable SDK)
    print("Connecting to Gemini 1.5-Flash (Stable)...")
    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        today = datetime.now().strftime("%A, %B %d, %Y")
        
        prompt = f"""
        Today's Date: {today}
        Extract game events from these Discord messages for the game "Predecessor".
        
        Messages:
        {combined_text}

        RULES:
        1. Identify the ACTUAL event start dates.
        2. Format as a valid JSON list of objects only.
        
        OUTPUT FORMAT:
        [
          {{"date": "YYYY-MM-DD", "title": "Event Name", "type": "patch/news", "url": "link", "image": "img_link"}}
        ]
        """
        
        response = model.generate_content(prompt)
        
        # Clean text and extract JSON
        raw_text = response.text
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if json_match:
            events = json.loads(json_match.group(0))
        else:
            events = []

        # 3. Write Output
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "events": events
        }
        
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        
        print(f"SUCCESS: Captured {len(events)} events.")

    except Exception as e:
        print(f"AI ERROR: {e}")
        # Ensure file exists to prevent Action crash
        if not os.path.exists('events.json'):
            with open('events.json', 'w') as f:
                json.dump({"events": []}, f)

if __name__ == "__main__":
    scrape()
