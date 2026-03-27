import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

URL = "https://www.predecessorgame.com/en-US/news"
BASE_URL = "https://www.predecessorgame.com"

# --- VERIFIED SAFETY NET ---
# We use the EXACT working links you provided here.
# The scraper will NOT overwrite these if it finds them on the site.
FALLBACK_EVENTS = [
    {
        "date": "2026-03-05", 
        "title": "V1.12.4 Patch Notes", 
        "type": "patch", 
        "url": "https://www.predecessorgame.com/en-US/news/patch-notes/v1-12-4-patchnotes", # Fixed
        "desc": "Balance fixes and PCC tournament prep."
    },
    {
        "date": "2026-03-17", 
        "title": "V1.12.6 Patch Notes", 
        "type": "patch", 
        "url": "https://www.predecessorgame.com/en-US/news/patch-notes/v1-12-6-patchnotes", # Fixed
        "desc": "Current live build fixes."
    },
    {
        "date": "2026-03-04", 
        "title": "Daybreak Map Update", 
        "type": "news", 
        "url": "https://www.predecessorgame.com/en-US/news/dev-diary/daybreak-introduction", 
        "desc": "New map reveal."
    }
]

def sanitize_url(url):
    """
    Omeda often switches between '-patch-notes' and '-patchnotes'.
    This helper tries to ensure we use the most common working format.
    """
    if "v1-" in url.lower() and url.endswith("-patch-notes"):
        # If the hyphenated one fails for you, we force the non-hyphenated version
        return url.replace("-patch-notes", "-patchnotes")
    return url

def clean_date(text):
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
    print("Scraping with Priority Logic...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    # Load fallbacks first
    events = list(FALLBACK_EVENTS)
    
    try:
        response = requests.get(URL, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for card in soup.find_all('a', href=re.compile(r'/news/')):
            title_tag = card.find(['h2', 'h3', 'h4', 'p'])
            if not title_tag: continue
            
            title = title_tag.get_text().strip()
            if len(title) < 5: continue 
            
            # Date detection
            time_tag = card.find('time')
            raw_date = time_tag['datetime'] if time_tag and time_tag.has_attr('datetime') else card.get_text()
            found_date = clean_date(raw_date)
            
            if found_date:
                raw_url = BASE_URL + card['href'] if card['href'].startswith('/') else card['href']
                final_url = sanitize_url(raw_url)
                
                # PRIORITY CHECK: 
                # If we already have a manual entry for this TITLE or DATE, skip the scraped one.
                if not any(e['title'] == title for e in events):
                    events.append({
                        "date": found_date,
                        "title": title,
                        "url": final_url,
                        "type": "patch" if "patch" in title.lower() else "news",
                        "desc": "Official Update"
                    })

        with open('events.json', 'w') as f:
            json.dump(events, f, indent=4)
        print(f"Success! {len(events)} events saved.")

    except Exception as e:
        print(f"Error: {e}")
        with open('events.json', 'w') as f:
            json.dump(events, f, indent=4)

if __name__ == "__main__":
    scrape()
