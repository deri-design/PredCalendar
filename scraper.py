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
    print("--- AI Agent: Temporal Sync Start ---")
    
    # 1. Fetch Discord Messages
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=15"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"DISCORD ERROR: {response.status_code}")
        return

    messages = response.json()
    print(f"Read {len(messages)} messages.")

    combined_text = ""
    for m in messages:
        combined_text += f"SENT: {m['timestamp']} | MSG: {m['content']}\n---\n"

    # 2. Consult Gemini (Using REST transport to fix 404)
    print("Connecting to Gemini AI Engine...")
    try:
        # Use REST transport to ensure compatibility with GitHub Runners
        genai.configure(api_key=GEMINI_KEY, transport='rest')
        
        # Use the most stable model identifier
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        today = datetime.now().strftime("%A, %B %d, %Y")
        
        prompt = f"""
        Today is {today}. Extract game events for "Predecessor" from these Discord messages.
        
        Messages:
        {combined_text}

        Return ONLY a JSON list of objects:
        [
          {{"date": "YYYY-MM-DD", "title": "Event Name", "type": "patch/news", "url": "link", "image": "img_url"}}
        ]
        """
        
        response = model.generate_content(prompt)
        
        # Extract JSON list from AI response
        raw_text = response.text
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        
        if json_match:
            events = json.loads(json_match.group(0))
            print(f"SUCCESS: AI identified {len(events)} events.")
        else:
            print("AI didn't find any events in the text.")
            events = []

        # 3. Save Output
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "events": events
        }
        
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)

    except Exception as e:
        print(f"AI SYSTEM ERROR: {e}")
        # Always ensure events.json exists
        if not os.path.exists('events.json'):
            with open('events.json', 'w') as f:
                json.dump({"events": []}, f)

if __name__ == "__main__":
    scrape()
