import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

URL = "https://www.predecessorgame.com/en-US/news"
BASE_URL = "https://www.predecessorgame.com"

def parse_date(date_text):
    # Converts "March 17, 2026" to "2026-03-17"
    try:
        return datetime.strptime(date_text.strip(), "%B %d, %Y").strftime("%Y-%m-%d")
    except:
        return datetime.now().strftime("%Y-%m-%d")

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(URL, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    events = []
    
    # Look for all news cards
    # Note: Predecessor's site uses specific tags for news items
    articles = soup.find_all('a', href=re.compile(r'/news/'))
    
    for art in articles:
        title_tag = art.find(['h2', 'h3', 'p'])
        date_tag = art.find_next('span') # Dates are usually in span tags near titles
        
        if title_tag:
            title = title_tag.get_text().strip()
            link = art['href']
            
            # Simple logic: If we find a date string in the text nearby
            raw_date = date_tag.get_text() if date_tag else ""
            clean_date = parse_date(raw_date) if "," in raw_date else datetime.now().strftime("%Y-%m-%d")
            
            events.append({
                "date": clean_date,
                "title": title,
                "url": BASE_URL + link if link.startswith('/') else link,
                "type": "patch" if "patch" in title.lower() else "season"
            })

    # Save unique events only
    unique_events = list({v['url']: v for v in events}.values())
    
    with open('events.json', 'w') as f:
        json.dump(unique_events, f, indent=4)

if __name__ == "__main__":
    scrape()
