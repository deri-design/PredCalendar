import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

URL = "https://www.predecessorgame.com/en-US/news"
BASE_URL = "https://www.predecessorgame.com"

# --- VERIFIED SAFETY NET ---
# These stay exactly as they are. The scraper will skip these URLs if found on site.
FALLBACK_EVENTS = [
    {
        "date": "2026-03-05", 
        "title": "V1.12.4 Patch Notes", 
        "type": "patch", 
        "url": "https://www.predecessorgame.com/en-US/news/patch-notes/v1-12-4-patchnotes",
        "desc": "Verified official patch notes link."
    },
    {
        "date": "2026-03-17", 
        "title": "V1.12.6 Patch Notes", 
        "type": "patch", 
        "url": "https://www.predecessorgame.com/en-US/news/patch-notes/v1-12-6-patchnotes",
        "desc": "Verified official patch notes link."
    },
    {
        "date": "2026-03-04", 
        "title": "Daybreak Map Update", 
        "type": "news", 
        "url": "https://www.predecessorgame.com/en-US/news/dev-diary/daybreak-introduction", 
        "desc": "Verified official dev diary link."
    }
]

def clean_date(text):
    # Regex to find: "March 17, 2026" or "Mar 17 2026"
    match = re.search(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', text)
    if match:
        mon, day, year = match.groups()
        mon = mon[:3].capitalize()
        try:
            dt = datetime.strptime(f"{mon} {day} {year}", "%b %d %Y")
            return dt.strftime("%Y-%m-%d")
        except: pass
    return None

def scrape():
    print("Executing Ultra-Aggressive Scrape...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    
    # Initialize with our verified safety net
    events = list(FALLBACK_EVENTS)
    verified_urls = [e['url'] for e in events]
    
    try:
        response = requests.get(URL, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find every link pointing to a news article
        all_links = soup.find_all('a', href=re.compile(r'/news/'))
        print(f"Found {len(all_links)} potential news links on page.")

        for card in all_links:
            raw_url = card['href']
            full_url = BASE_URL + raw_url if raw_url.startswith('/') else raw_url
            
            # 1. Fix URL inconsistency automatically
            if "-patch-notes" in full_url and "v1-" in full_url:
                full_url = full_url.replace("-patch-notes", "-patchnotes")

            # 2. Skip if we already have this URL in our Fallback/Verified list
            if full_url in verified_urls:
                continue

            # 3. Extract Title (The first long string of text found)
            # We look for the text inside the card that isn't the date
            card_text = card.get_text(separator='|').split('|')
            card_text = [t.strip() for t in card_text if len(t.strip()) > 1]
            
            title = "New Update"
            found_date = None
            
            for segment in card_text:
                d = clean_date(segment)
                if d:
                    found_date = d
                elif len(segment) > 10 and title == "New Update":
                    title = segment

            # 4. If we found a date, save the event
            if found_date:
                events.append({
                    "date": found_date,
                    "title": title,
                    "url": full_url,
                    "type": "patch" if "patch" in title.lower() else "news",
                    "desc": "Official Website Sync"
                })
                verified_urls.append(full_url)
                print(f"Added: {title} ({found_date})")

        # Save to JSON
        with open('events.json', 'w') as f:
            json.dump(events, f, indent=4)
        print(f"Success! Total events in JSON: {len(events)}")

    except Exception as e:
        print(f"Scrape Error: {e}")
        with open('events.json', 'w') as f:
            json.dump(events, f, indent=4)

if __name__ == "__main__":
    scrape()
