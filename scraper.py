import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

URL = "https://www.predecessorgame.com/en-US/news"
BASE_URL = "https://www.predecessorgame.com"

# The "Safety Net": These events will ALWAYS stay on your calendar
# even if the scraper fails to find them on the news page.
FALLBACK_EVENTS = [
    {"date": "2026-02-18", "title": "V1.12 Patch Notes", "type": "patch", "url": "https://www.predecessorgame.com/en-US/news/patch-notes/v1-12-patch-notes", "desc": "Major Season 3 overhaul."},
    {"date": "2026-03-04", "title": "Daybreak Map Update", "type": "news", "url": "https://www.predecessorgame.com/en-US/news/dev-diary/daybreak-introduction", "desc": "New map reveal."},
    {"date": "2026-03-05", "title": "V1.12.4 Patch Notes", "type": "patch", "url": "https://www.predecessorgame.com/en-US/news/patch-notes/v1-12-4-patch-notes", "desc": "Balance fixes."},
    {"date": "2026-03-17", "title": "V1.12.6 Patch Notes", "type": "patch", "url": "https://www.predecessorgame.com/en-US/news/patch-notes/v1-12-6-patch-notes", "desc": "Current live build."},
    {"date": "2026-03-25", "title": "Refer-a-Friend Competition", "type": "news", "url": "https://www.predecessorgame.com/en-US/news/events/friend-reward-competition", "desc": "Win a Secretlab chair!"}
]

def clean_date(text):
    # Aggressive date search for formats like "March 17, 2026" or "17 Mar 2026"
    text = text.replace(',', ' ')
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    
    match = re.search(r'([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})', text)
    if not match:
        match = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', text)
        
    if match:
        parts = match.groups()
        mon_str = next((m for m in months if m in parts[0].lower() or m in parts[1].lower()), None)
        day = next((d for d in parts if d.isdigit() and len(d) <= 2), "01")
        year = next((y for y in parts if y.isdigit() and len(y) == 4), "2026")
        
        if mon_str:
            try:
                dt = datetime.strptime(f"{mon_str.capitalize()} {day} {year}", "%b %d %Y")
                return dt.strftime("%Y-%m-%d")
            except: pass
    return None

def scrape():
    print("Scraping Predecessor News...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    events = list(FALLBACK_EVENTS) # Start with our verified events
    
    try:
        response = requests.get(URL, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for all links that likely point to news articles
        for card in soup.find_all('a', href=re.compile(r'/news/')):
            title_tag = card.find(['h2', 'h3', 'h4', 'p'])
            if not title_tag: continue
            
            title = title_tag.get_text().strip()
            # Skip if title is too short or just 'News'
            if len(title) < 5: continue 
            
            # Check for date in the card text or in a <time> tag
            time_tag = card.find('time')
            raw_date = time_tag['datetime'] if time_tag and time_tag.has_attr('datetime') else card.get_text()
            
            found_date = clean_date(raw_date)
            
            if found_date:
                full_url = BASE_URL + card['href'] if card['href'].startswith('/') else card['href']
                # Avoid adding duplicates from the fallback list
                if not any(e['url'] == full_url for e in events):
                    events.append({
                        "date": found_date,
                        "title": title,
                        "url": full_url,
                        "type": "patch" if "patch" in title.lower() else "news",
                        "desc": "Official News Update"
                    })

        # Final cleanup and save
        with open('events.json', 'w') as f:
            json.dump(events, f, indent=4)
        print(f"Success! Saved {len(events)} events to events.json")

    except Exception as e:
        print(f"Scrape encountered an error: {e}")
        # Even if error, save the fallbacks so the site isn't empty
        with open('events.json', 'w') as f:
            json.dump(events, f, indent=4)

if __name__ == "__main__":
    scrape()
