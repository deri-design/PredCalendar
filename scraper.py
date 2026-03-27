import os
import requests
import json
import re
from groq import Groq
from datetime import datetime

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
CHANNEL_ID = "1487129767865225261"

def ask_groq(text):
    client = Groq(api_key=GROQ_KEY)
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"Today is {today}. Extract game events for 'Predecessor' from these Discord messages. Return ONLY a JSON list: [{{'date': 'YYYY-MM-DD', 'title': 'name', 'type': 'patch/news', 'url': 'link', 'image': 'img'}}]. Text: {text}"
    
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content).get('events', []) # or similar structure
