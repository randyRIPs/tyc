from flask import Flask, render_template, request, make_response, jsonify
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
    url = "http://www.atmovies.com.tw/movie/next/"
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers, timeout=10)
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")

    movie_items = soup.select(".filmListAllX li")
    update_tag = soup.find(class_="smaller09")

    if not update_tag:
        return "找不到網站更新日期"

    last_update = update_tag.text[5:]

    for item in movie_items:
        img = item.find("img")
        title_block = item.find("div", class_="filmtitle")
        runtime_block = item.find(class_="runtime")

        if not img or not title_block or not runtime_block:
            continue

        picture = img.get("src", "").replace(" ", "")

        if picture.startswith("//"):
            picture = "https:" + picture
        elif picture.startswith("/"):
            picture = "http://www.atmovies.com.tw" + picture

        title = img.get("alt", "").strip()

        link_tag = title_block.find("a")
        if not link_tag:
            continue

        movie_id = link_tag.get("href", "").replace("/", "").replace("movie", "")
        hyperlink = "http://www.atmovies.com.tw" + link_tag.get("href", "")

        runtime_text = runtime_block.text.strip()
        show_date = runtime_text[5:15] if len(runtime_text) >= 15 else ""

        show_length = ""
        if "片長" in runtime_text and "分" in runtime_text:
            start = runtime_text.find("片長")
            end = runtime_text.find("分")
            show_length = runtime_text[start + 3:end]

        rate = ""
        rate_img = runtime_block.find("img")

        if rate_img:
            rate_code = (
                rate_img.get("src", "")
                .replace("/images/cer_", "")
                .replace(".gif", "")
            )

            rate = {
                "G": "普遍級",
                "P": "保護級",
                "F2": "輔12級",
                "F5": "輔15級"
            }.get(rate_code, "限制級")

        movie_data = {
            "title": title,
            "picture": picture,
            "hyperlink": hyperlink,
            "showDate": show_date,
            "showLength": show_length,
            "rate": rate,
            "lastUpdate": last_update
        }

        if movie_id:
            db.collection("電影含分級").document(movie_id).set(movie_data)

    return "近期上映電影已爬蟲及存檔完畢，網站最近更新日期為：" + last_update


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

        docs = db.collection("電影含分級").where("rate", "==", rate_value).stream()

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

    info = "動作：" + action + "； 查詢內容：" + msg

    return make_response(jsonify({
        "fulfillmentText": info
    }))


if __name__ == "__main__":
    app.run(debug=True)