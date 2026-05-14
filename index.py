from flask import Flask, render_template, request, make_response, jsonify
from rate import crawl_and_save_movies
import firebase_admin
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup
from spider import get_movies
import os
import json
from opendata import get_roads
from weather import get_weather

app = Flask(__name__)


def init_firebase():
    if firebase_admin._apps:
        return firestore.client()

    firebase_key = os.environ.get("FIREBASE_KEY")

    if firebase_key:
        cred_dict = json.loads(firebase_key)
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate("serviceAccountKey.json")

    firebase_admin.initialize_app(cred)
    return firestore.client()


db = init_firebase()


@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="zh-Hant">
    <head>
        <meta charset="UTF-8">
        <title>羅翊綸的網頁</title>
    </head>
    <body>
        <h2>羅翊綸的網頁</h2>

        <a href="/weather">
            <button>台灣天氣查詢</button>
        </a>
        
        <br><br>

        <a href="/roadsearch">
            <button>台中易肇事路口查詢</button>
        </a>

        <br><br>
        <a href="/movie">
            <button>電影查詢</button>
        </a>
        <br><br>

        <a href="/rate">
            <button>爬取並存入電影資料</button>
        </a>
    </body>
    </html>
    """


@app.route("/weather", methods=["GET", "POST"])
def weather():
    result = None

    if request.method == "POST":
        city = request.form.get("city", "").strip()

        if city:
            result = get_weather(city)

    return render_template("weather.html", result=result)


@app.route("/roadsearch")
def roadsearch():
    result = get_roads()
    return render_template("roadsearch.html", result=result)


@app.route("/movie", methods=["GET", "POST"])
def movie():
    result = []

    if request.method == "POST":
        keyword = request.form.get("keyword", "").strip()

        if keyword:
            docs = db.collection("電影含分級").order_by("showDate").stream()

            for doc in docs:
                data = doc.to_dict()
                title = data.get("title", "")

                if keyword in title:
                    result.append({
                        "title": title,
                        "url": data.get("hyperlink", ""),
                        "date": data.get("showDate", ""),
                        "length": data.get("showLength", ""),
                        "rate": data.get("rate", ""),
                        "picture": data.get("picture", "")
                    })

            if not result:
                crawler_result = get_movies(keyword)

                for movie_data in crawler_result:
                    result.append({
                        "title": movie_data.get("title", ""),
                        "url": movie_data.get("url", ""),
                        "date": movie_data.get("date", ""),
                        "length": "",
                        "rate": "",
                        "picture": movie_data.get("picture", "")
                    })

    return render_template("movie.html", result=result)


@app.route("/rate")
def rate():
    return crawl_and_save_movies(db)


@app.route("/webhook", methods=["POST"])
def webhook():
    req = request.get_json(force=True)

    query_result = req.get("queryResult", {})
    action = query_result.get("action", "")
    msg = query_result.get("queryText", "")
    parameters = query_result.get("parameters", {})

    rate_value = parameters.get("rate", "")

    if action == "rateChoice":
        if not rate_value:
            return make_response(jsonify({
                "fulfillmentText": "請告訴我你想查哪一種電影分級，例如：普遍級、保護級、輔12級、輔15級、限制級。"
            }))

        movies = []

        docs = db.collection("電影含分級").limit(5).stream()

        for doc in docs:
            data = doc.to_dict()
            title = data.get("title", "")
            show_date = data.get("showDate", "")
            movie_rate = data.get("rate", "")

            if title:
                movies.append(f"{title}｜上映日期：{show_date}｜分級：{movie_rate}")

        if not movies:
            return make_response(jsonify({
                "fulfillmentText": f"目前找不到{rate_value}的電影資料，請先到網站按「爬取並存入電影資料」更新資料。"
            }))

        text = f"找到以下{rate_value}電影：\n" + "\n".join(movies[:5])

        return make_response(jsonify({
            "fulfillmentText": text
        }))

    info = "我是翊綸設計的機器人，動作：" + action + "； 查詢內容：" + msg

    return make_response(jsonify({
        "fulfillmentText": info
    }))


if __name__ == "__main__":
    app.run(debug=True)