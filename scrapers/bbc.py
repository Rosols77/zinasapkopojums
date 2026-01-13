import requests
from bs4 import BeautifulSoup

def scrape_bbc():
    url = "http://feeds.bbci.co.uk/news/rss.xml"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "xml")  # XML parser ar lxml

    articles = []

    items = soup.find_all("item")[:10]
    for item in items:
        title = item.title.get_text(strip=True)
        articles.append({
            "title": title,
            "source": "BBC"
        })

    return articles
