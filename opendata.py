import requests

def get_roads():

    url = "https://datacenter.taichung.gov.tw/swagger/OpenData/a1b899c0-511f-4e3d-b22b-814982a97e41"

    response = requests.get(url)

    data = response.json()

    result = []

    for item in data:

        result.append({
            "road": item.get("路口名稱", ""),
            "count": item.get("總件數", ""),
            "reason": item.get("主要肇因", "")
        })

    return result