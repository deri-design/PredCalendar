import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

URL = "https://www.predecessorgame.com/en-US/news"
BASE_URL = "https://www.predecessorgame.com"

def scrape():
    print("Starting scrape...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(URL, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        events = []
        
        # Predecessor site uses <a> tags that contain both the date and title
        cards = soup.find_all('a', href=re.compile(r'/news/'))
        
        for card in cards:
            # Look for date text (e.g., "March 17, 2026")
            # Usually found in a span or small tag inside the card
            date_text = ""
            for tag in card.find_all(['span', 'p', 'div']):
                txt = tag.get_text().strip()
                if re.search(r'[A-Z][a-z]+ \d{1,2}, \d{4}', txt):
                    date_text = txt
                    break
            
            # Look for the title (usually h2 or h3)
            title_tag = card.find(['h2', 'h3', 'h4'])
            title_text = title_tag.get_text().strip() if title_tag else "New Update"
            
            if date_text:
                try:
                    # Convert "March 17, 2026" -> "2026-03-17"
                    clean_date = datetime.strptime(date_text, "%B %d, %Y").strftime("%Y-%m-%d")
                    
                    events.append({
                        "date": clean_date,
                        "title": title_text,
                        "url": BASE_URL + card['href'] if card['href'].startswith('/') else card['href'],
                        "type": "patch" if "patch" in title_text.lower() else "news"
                    })
                except Exception as e:
                    print(f"Date error: {e}")

        # Unique entries only
        final_list = list({v['url']: v for v in events}.values())
        
        with open('events.json', 'w') as f:
            json.dump(final_list, f, indent=4)
        
        print(f"Success! Found {len(final_list)} events.")

    except Exception as e:
        print(f"Scrape failed: {e}")

if __name__ == "__main__":
    scrape()
