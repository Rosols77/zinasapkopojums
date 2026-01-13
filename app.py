from flask import Flask, render_template
from scrapers.bbc import scrape_bbc
from scrapers.guardian import scrape_guardian
from scrapers.cnn import scrape_cnn

app = Flask(__name__)

@app.route("/")
def home():
    news = []
    news.extend(scrape_bbc())
    news.extend(scrape_guardian())
    news.extend(scrape_cnn())
    return render_template("index.html", news=news)

if __name__ == "__main__":
    app.run(debug=True)
