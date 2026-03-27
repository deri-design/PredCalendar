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
        print(f"DISCORD ERROR: {res.status_code} - {res.text}")
        return []
    return res.json()

def list_available_models():
    """Diagnostic: Prints all models your API key can access"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    res = requests.get(url)
    if res.status_code == 200:
        print("--- DEBUG: YOUR AVAILABLE MODELS ---")
        models = res.json().get('models', [])
        for m in models:
            print(f"Model Found: {m['name']}")
        print("------------------------------------")
    else:
        print(f"Model List Error: {res.status_code} - {res.text}")

def ask_gemini(messages_text):
    # Try the v1beta endpoint - this is the standard for 1.5-flash
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""
    Today is {today}. Context: Game "Predecessor".
    Extract event dates from these Discord messages.
    Rules: 
    1. Identify ACTUAL start dates.
    2. Format as JSON list only: [{{"date":"YYYY-MM-DD","title":"Name","type":"patch/news"}}]
    
    Messages:
    {messages_text}
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    response = requests.post(api_url, json=payload)
    
    if response.status_code != 200:
        print(f"AI API ERROR: {response.status_code} - {response.text}")
        list_available_models() # Run diagnostic on failure
        return None

    data = response.json()
    try:
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        return json.loads(json_match.group(0))
    except Exception as e:
        print(f"JSON Parsing Error: {e}")
        print(f"Raw AI Response: {data}")
        return None

def scrape():
    print("AI Agent: Starting Sync...")
    
    # 1. Get Discord Data
    messages = get_discord_messages()
    if not messages: return

    combined = ""
    for m in messages:
        combined += f"SENT: {m['timestamp']} | MSG: {m['content']}\n---\n"

    # 2. Get AI Prediction
    events = ask_gemini(combined)
    
    if events is not None:
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "events": events
        }
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"AI SUCCESS: {len(events)} events extracted.")
    else:
        print("AI FAILURE: No data written to events.json")

if __name__ == "__main__":
    scrape()
