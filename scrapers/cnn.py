import requests
from bs4 import BeautifulSoup

def scrape_cnn():
    url = "https://edition.cnn.com/world"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    articles = []
    for item in soup.select("h3.cd__headline a"):
        title = item.get_text(strip=True)
        link = item.get("href")
        if link and link.startswith("/"):
            link = "https://edition.cnn.com" + link
        if title and link:
            articles.append({"title": title, "source": "CNN", "link": link})
    return articles[:10]
