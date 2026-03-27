import requests
import re
import json
from datetime import datetime

# URL of the news page
URL = "https://www.predecessorgame.com/en-US/news"
BASE_URL = "https://www.predecessorgame.com"

def scrape():
    response = requests.get(URL)
    html = response.text
    
    # We find article links and titles using Regex
    # Pattern looks for: /en-US/news/subdirectory/slug
    links = re.findall(r'href="(/en-US/news/[^"]+)"[^>]*><h[^>]*>([^<]+)', html)
    
    events = []
    for link, title in links:
        # Note: Predecessor's website usually puts dates in the URL or metadata
        # For this simple version, we'll try to find any YYYY-MM-DD pattern
        # or just use today's date if one isn't found (Improvement: use actual meta tags)
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', html)
        date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")
        
        events.append({
            "date": date_str,
            "title": title.strip(),
            "url": BASE_URL + link,
            "type": "patch" if "patch" in title.lower() else "season"
        })
    
    with open('events.json', 'w') as f:
        json.dump(events, f, indent=4)

if __name__ == "__main__":
    scrape()