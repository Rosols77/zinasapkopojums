from flask import Flask, render_template
from scrapers.bbc import scrape_bbc

app = Flask(__name__)


@app.route("/")
def home():
    # Iegūst BBC ziņas
    news = scrape_bbc()

    # Padod ziņas HTML lapai
    return render_template("index.html", news=news)


if __name__ == "__main__":
    # Palaid serveri lokāli
    app.run(debug=True)
