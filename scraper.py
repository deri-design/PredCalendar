import os
import requests
import json
import google.generativeai as genai
from datetime import datetime

# Configuration from GitHub Secrets
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "1487129767865225261" # Predecessor Official Announcements ID

def get_discord_messages():
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
    # Fetch last 20 messages
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=20"
    response = requests.get(url, headers=headers)
    return response.json()

def ask_gemini_for_roadmap(messages_text):
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-pro')
    
    today = datetime.now().strftime("%A, %B %d, %Y")
    
    prompt = f"""
    Today's Date: {today}
    You are an expert at extracting game roadmap dates from Discord announcements.
    
    Read these Discord messages from the game "Predecessor":
    ---
    {messages_text}
    ---
    
    TASK:
    1. Extract every planned event, patch, or hero release.
    2. Determine the ACTUAL START DATE. If a post says "This Tuesday" and the post was March 24, the date is 2026-03-31.
    3. If no year is mentioned, assume 2026.
    4. Categorize as "patch" or "news".
    5. Look for any image URLs or website links inside the messages.
    
    OUTPUT FORMAT (Strict JSON list only):
    [
      {{"date": "YYYY-MM-DD", "title": "Event Name", "type": "patch/news", "url": "link", "image": "img_link"}}
    ]
    """
    
    response = model.generate_content(prompt)
    # Clean the response text to ensure it's just the JSON list
    json_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(json_text)

def scrape():
    print("Fetching Discord announcements...")
    messages = get_discord_messages()
    
    combined_text = ""
    for m in messages:
        combined_text += f"POSTED: {m['timestamp']} | CONTENT: {m['content']}\n---\n"

    print("Gemini AI is processing dates...")
    events = ask_gemini_for_roadmap(combined_text)
    
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "events": events
    }

    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"Success: Gemini identified {len(events)} events.")

if __name__ == "__main__":
    scrape()
