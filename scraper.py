import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

URL = "https://www.predecessorgame.com/en-US/news"
BASE_URL = "https://www.predecessorgame.com"

def clean_date(text):
    # Try to find a date pattern in text: "March 17, 2026" or "Mar 17, 2026"
    match = re.search(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', text)
    if match:
        mon, day, year = match.groups()
        # Standardize month to first 3 letters for parsing
        mon = mon[:3].capitalize()
        try:
            dt = datetime.strptime(f"{mon} {day} {year}", "%b %d %Y")
            return dt.strftime("%Y-%m-%d")
        except:
            pass
    return None

def scrape():
    print("Starting deep scrape...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
    
    try:
        response = requests.get(URL, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        events = []
        
        # Look for article cards (usually <a> tags wrapping the news)
        cards = soup.find_all('a', href=re.compile(r'/news/'))
        
        for card in cards:
            title_tag = card.find(['h2', 'h3', 'h4'])
            if not title_tag: continue
            
            title = title_tag.get_text().strip()
            link = card['href']
            
            # 1. Try to find a <time> tag with a datetime attribute (Best method)
            time_tag = card.find('time')
            found_date = None
            
            if time_tag and time_tag.has_attr('datetime'):
                found_date = time_tag['datetime'][:10] # Grab YYYY-MM-DD
            
            # 2. Fallback: Search all text inside the card for a date string
            if not found_date:
                found_date = clean_date(card.get_text())

            if found_date:
                events.append({
                    "date": found_date,
                    "title": title,
                    "url": BASE_URL + link if link.startswith('/') else link,
                    "type": "patch" if "patch" in title.lower() else "news"
                })
            else:
                print(f"Could not find date for: {title}")

        # Remove duplicates
        final_list = list({v['url']: v for v in events}.values())
        
        with open('events.json', 'w') as f:
            json.dump(final_list, f, indent=4)
        
        print(f"Success! Captured {len(final_list)} events with valid dates.")

    except Exception as e:
        print(f"Scrape failed: {e}")

if __name__ == "__main__":
    scrape()
