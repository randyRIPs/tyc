from flask import Flask, render_template, request, make_response, jsonify
from rate import crawl_and_save_movies
import firebase_admin
from firebase_admin import credentials, firestore
from spider import get_movies
import os
import json
from opendata import get_roads
from weather import get_weather

from google import genai
from google.genai import types

app = Flask(__name__)

client = genai.Client()


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

        <script src="https://www.gstatic.com/dialogflow-console/fast/messenger/bootstrap.js?v=1"></script>
        <df-messenger
            chat-title="home"
            agent-id="9c31906e-73fa-41b1-a3c0-493ea75e5ff5"
            language-code="zh-tw">
        </df-messenger>
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

    action = req.get("queryResult", {}).get("action", "")
    info = "查詢失敗"

    if action == "rateChoice":
        rate = req.get("queryResult", {}).get("parameters", {}).get("rate", "")

        info = "我是羅翊綸開發的電影聊天機器人，您選擇的電影分級是：" + rate + "\n\n相關電影：\n\n"

        collection_ref = db.collection("電影含分級")
        docs = collection_ref.get()

        result = ""

        for doc in docs:
            data = doc.to_dict()

            if "rate" in data and rate in data["rate"]:
                result += "片名：" + data.get("title", "未知") + "\n"
                result += "電影網址：" + data.get("hyperlink", "無") + "\n\n"

        if result == "":
            result = "目前查無相關電影"

        info += result

    elif action == "MovieDetail":
        question = req.get("queryResult", {}).get("parameters", {}).get("FilmQ", "")
        keyword = req.get("queryResult", {}).get("parameters", {}).get("any", "")

        info = "我是羅翊綸開發的電影聊天機器人，您要查詢電影的" + question + "，關鍵字是：" + keyword + "\n\n"

        collection_ref = db.collection("電影含分級")
        docs = collection_ref.get()

        found = False

        for doc in docs:
            data = doc.to_dict()
            title = data.get("title", "")

            if keyword in title:
                found = True

                if question == "片名":
                    info += "片名：" + data.get("title", "未知") + "\n"
                    info += "海報：" + data.get("picture", "無") + "\n"
                    info += "影片介紹：" + data.get("hyperlink", "無") + "\n"
                    info += "片長：" + data.get("showLength", "未知") + " 分鐘\n"
                    info += "分級：" + data.get("rate", "未知") + "\n"
                    info += "上映日期：" + data.get("showDate", "未知") + "\n\n"

                elif question == "片長":
                    info += "片名：" + data.get("title", "未知") + "\n"
                    info += "片長：" + data.get("showLength", "未知") + " 分鐘\n\n"

                else:
                    info += "片名：" + data.get("title", "未知") + "\n"
                    info += "片長：" + data.get("showLength", "未知") + " 分鐘\n"
                    info += "分級：" + data.get("rate", "未知") + "\n"
                    info += "上映日期：" + data.get("showDate", "未知") + "\n\n"

        if not found:
            info += "很抱歉，目前無符合這個關鍵字的相關電影喔"

    elif action == "input.unknown":
        user_question = req.get("queryResult", {}).get("queryText", "")

        instruction_text = (
            "你是一個熱心且知識豐富的專業智慧助理。"
            "請使用繁體中文回答。"
            "回答要簡潔、清楚，抓重點，不要重述使用者問題。"
        )

        ai_config = types.GenerateContentConfig(
            max_output_tokens=500,
            system_instruction=instruction_text
        )

        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=user_question,
                config=ai_config
            )

            if response.text:
                info = response.text
            else:
                info = "抱歉，我現在無法生成回應，請稍後再試。"

        except Exception as e:
            info = "Gemini 回應發生錯誤：" + str(e)

    return make_response(jsonify({
        "fulfillmentText": info
    }))


if __name__ == "__main__":
    app.run(debug=True)