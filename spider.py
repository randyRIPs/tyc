import requests
from bs4 import BeautifulSoup

def get_movies(keyword):
    url = "http://www.atmovies.com.tw/movie/next/"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(".filmListAllX li")
        movies = []

        for item in items:
            title_tag = item.select_one(".filmtitle")
            if not title_tag:
                continue
            title = title_tag.text.strip()
            if keyword in title:
                link = "http://www.atmovies.com.tw" + title_tag.a["href"]
                date_tag = item.select_one(".runtime")
                date = date_tag.text.strip() if date_tag else "未提供"
                movies.append({
                    "title": title,
                    "url": link,
                    "date": date
                })

        return movies

    except:
        return []

