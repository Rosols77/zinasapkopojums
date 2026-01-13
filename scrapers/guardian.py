import requests
from bs4 import BeautifulSoup

def scrape_guardian():
    url = "https://www.theguardian.com/world"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    articles = []
    for item in soup.select("a.js-headline-text"):
        title = item.get_text(strip=True)
        link = item.get("href")
        if title and link:
            articles.append({"title": title, "source": "The Guardian", "link": link})
    return articles[:10]
