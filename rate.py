import requests
from bs4 import BeautifulSoup

def crawl_and_save_movies(db):
    url = "https://www.atmovies.com.tw/movie/new/"
    headers = {"User-Agent": "Mozilla/5.0"}

    data = requests.get(url, headers=headers, timeout=10)
    data.encoding = "utf-8"

    sp = BeautifulSoup(data.text, "html.parser")

    update_tag = sp.find(class_="smaller09")
    if not update_tag:
        return "找不到網站更新日期"

    last_update = update_tag.text[5:]

    result = sp.select(".filmList")

    for x in result:
        title = x.find("a").text.strip()
        introduce = x.find("p").text.strip() if x.find("p") else ""

        movie_id = x.find("a").get("href").replace("/", "").replace("movie", "")
        hyperlink = "http://www.atmovies.com.tw/movie/" + movie_id
        picture = "https://www.atmovies.com.tw/photo101/" + movie_id + "/pm_" + movie_id + ".jpg"

        runtime = x.find(class_="runtime")
        runtime_text = runtime.text if runtime else ""

        rate = ""
        r = runtime.find("img") if runtime else None

        if r is not None:
            rr = r.get("src").replace("/images/cer_", "").replace(".gif", "")

            if rr == "G":
                rate = "普遍級"
            elif rr == "P":
                rate = "保護級"
            elif rr == "F2":
                rate = "輔12級"
            elif rr == "F5":
                rate = "輔15級"
            else:
                rate = "限制級"

        show_length = ""
        if "片長" in runtime_text and "分" in runtime_text:
            t1 = runtime_text.find("片長")
            t2 = runtime_text.find("分")
            show_length = runtime_text[t1 + 3:t2]

        show_date = ""
        if "上映日期" in runtime_text:
            t1 = runtime_text.find("上映日期")
            t2 = runtime_text.find("上映廳數")
            show_date = runtime_text[t1 + 5:t2 - 8]

        doc = {
            "title": title,
            "introduce": introduce,
            "picture": picture,
            "hyperlink": hyperlink,
            "showDate": show_date,
            "showLength": show_length,
            "rate": rate,
            "lastUpdate": last_update
        }

        if movie_id:
            db.collection("電影含分級").document(movie_id).set(doc)

    return "本週新片已爬蟲及存檔完畢，網站最近更新日期為：" + last_update