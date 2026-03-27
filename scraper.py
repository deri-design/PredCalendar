import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta

URL = "https://www.predecessorgame.com/en-US/news"
BASE_URL = "https://www.predecessorgame.com"

def get_clean_date(text):
    """Try various regex patterns to extract a valid YYYY-MM-DD date."""
    text = text.replace('|', ' ').replace('\n', ' ').strip()
    now = datetime.now()

    # 1. Handle "X days ago"
    if 'ago' in text.lower():
        num = re.findall(r'\d+', text)
        if num:
            n = int(num[0])
            if 'day' in text.lower(): return (now - timedelta(days=n)).strftime("%Y-%m-%d")
            if 'hour' in text.lower() or 'min' in text.lower(): return now.strftime("%Y-%m-%d")

    # 2. Handle "Mar 18, 2026" or "March 18, 2026"
    months = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December"
    match = re.search(fr'({months})\s+(\d{{1,2}}),?\s+(\d{{4}})', text, re.I)
    if match:
        mon, day, year = match.groups()
        try:
            dt = datetime.strptime(f"{mon[:3].capitalize()} {day} {year}", "%b %d %Y")
            return dt.strftime("%Y-%m-%d")
        except: pass
    
    return None

def scrape():
    print("--- Starting Advanced Scrape ---")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
    events = []
    
    try:
        response = requests.get(URL, headers=headers, timeout=20)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # METHOD A: Extract from the hidden JSON data (Most accurate)
        json_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                # Search recursively for any list that looks like news
                def find_news(obj):
                    if isinstance(obj, dict):
                        if 'newsList' in obj: return obj['newsList']
                        for v in obj.values():
                            res = find_news(v)
                            if res: return res
                    elif isinstance(obj, list):
                        for i in obj:
                            res = find_news(i)
                            if res: return res
                    return None
                
                news_data = find_news(data)
                if news_data:
                    for item in news_data:
                        date_raw = item.get('publishedAt') or item.get('createdAt') or ""
                        title = item.get('title', 'New Update')
                        slug = item.get('slug', '')
                        cat = item.get('category', {}).get('slug', 'news')
                        img = item.get('image', {}).get('url', '')
                        
                        link = f"{BASE_URL}/en-US/news/{cat}/{slug}"
                        if "patch" in title.lower(): link = link.replace("-patch-notes", "-patchnotes")
                        if img.startswith('/'): img = BASE_URL + img

                        events.append({
                            "date": date_raw[:10],
                            "title": title,
                            "url": link,
                            "image": img,
                            "type": "patch" if "patch" in title.lower() else "news"
                        })
            except: pass

        # METHOD B: HTML Scraping (Fallback for extra items)
        if len(events) < 5:
            articles = soup.find_all('a', href=re.compile(r'/news/'))
            for art in articles:
                title_tag = art.find(['h2', 'h3', 'h4', 'p'])
                if not title_tag: continue
                title = title_tag.get_text().strip()
                link = BASE_URL + art['href'] if art['href'].startswith('/') else art['href']
                
                # Check for duplicates
                if any(e['url'] == link for e in events): continue

                date_str = get_clean_date(art.get_text(separator='|'))
                if not date_str: date_str = datetime.now().strftime("%Y-%m-%d")

                img_tag = art.find('img')
                img_url = img_tag.get('src') if img_tag else ""
                if img_url.startswith('/'): img_url = BASE_URL + img_url

                events.append({
                    "date": date_str, "title": title, "url": link, "image": img_url, 
                    "type": "patch" if "patch" in title.lower() else "news"
                })

    except Exception as e:
        print(f"Error: {e}")

    # Final Output
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "events": events
    }
    with open('events.json', 'w') as f:
        json.dump(output, f, indent=4)
    print(f"Scrape Complete: {len(events)} events found.")

if __name__ == "__main__":
    scrape()
