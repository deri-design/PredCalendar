import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta

URL = "https://www.predecessorgame.com/en-US/news"
BASE_URL = "https://www.predecessorgame.com"

def get_actual_date(art_soup):
    """
    Looks specifically for the date string inside a Predecessor news card.
    Targets spans and p tags that contain month names or 'ago'.
    """
    text_blobs = art_soup.find_all(['span', 'p', 'time', 'div'])
    now = datetime.now()
    
    # 1. Check for <time> tag with datetime attribute
    time_tag = art_soup.find('time')
    if time_tag and time_tag.has_attr('datetime'):
        return time_tag['datetime'][:10]

    for blob in text_blobs:
        txt = blob.get_text().strip().lower()
        
        # 2. Handle relative dates like "2 days ago"
        if 'ago' in txt:
            nums = re.findall(r'\d+', txt)
            if nums:
                val = int(nums[0])
                if 'day' in txt: return (now - timedelta(days=val)).strftime("%Y-%m-%d")
                if 'hour' in txt or 'min' in txt: return now.strftime("%Y-%m-%d")
        
        # 3. Handle absolute dates like "Mar 18, 2026"
        # Regex looks for Month name + Day + Year
        match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})', txt)
        if match:
            mon, day, year = match.groups()
            try:
                dt = datetime.strptime(f"{mon.capitalize()} {day} {year}", "%b %d %Y")
                return dt.strftime("%Y-%m-%d")
            except: pass
            
    return None

def scrape():
    print("Starting Deep Scrape for Dates and Images...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
    
    try:
        response = requests.get(URL, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # All news items are wrapped in <a> tags linking to /news/
        articles = soup.find_all('a', href=re.compile(r'/news/'))
        print(f"Found {len(articles)} news items.")

        scraped_events = []
        for art in articles:
            # Title
            title_tag = art.find(['h2', 'h3', 'h4'])
            if not title_tag: continue
            title = title_tag.get_text().strip()
            
            # URL
            link = BASE_URL + art['href'] if art['href'].startswith('/') else art['href']
            
            # Image
            img_tag = art.find('img')
            img_url = ""
            if img_tag:
                img_url = img_tag.get('src') or img_tag.get('data-src') or ""
                if img_url.startswith('/'): img_url = BASE_URL + img_url

            # DATE (The critical fix)
            found_date = get_actual_date(art)
            
            # If we still can't find a date in the HTML, we look for one last place: the URL itself
            # Sometimes slugs contain dates like /2026/03/17/
            if not found_date:
                url_date = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', link)
                if url_date:
                    found_date = f"{url_date.group(1)}-{url_date.group(2)}-{url_date.group(3)}"
            
            # Final fallback to avoid clustering on the 27th
            if not found_date:
                found_date = "2026-03-01" 

            scraped_events.append({
                "date": found_date,
                "title": title,
                "url": link,
                "image": img_url,
                "type": "patch" if "patch" in title.lower() else "news"
            })

        # Save to file
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "events": scraped_events
        }
        with open('events.json', 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Success! {len(scraped_events)} events written.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape()
