import requests

def get_weather(city):

    city = city.replace("台", "臺")

    token = "rdec-key-123-45678-011121314"


    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"

    params = {
        "Authorization": token,
        "format": "JSON",
        "locationName": city
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        data = response.json()

        locations = data["records"]["location"]

        if not locations:
            return {
                "city": city,
                "data": [],
                "error": "查無資料"
            }

        location = locations[0]

        weather_data = []

        weather_times = location["weatherElement"][0]["time"]
        rain_times = location["weatherElement"][1]["time"]

        for i in range(len(weather_times)):

            weather_data.append({

                "start": weather_times[i]["startTime"],
                "end": weather_times[i]["endTime"],

                "weather":
                    weather_times[i]["parameter"]["parameterName"],

                "rain":
                    rain_times[i]["parameter"]["parameterName"]
            })

        return {
            "city": city,
            "data": weather_data,
            "error": ""
        }

    except Exception as e:

        return {
            "city": city,
            "data": [],
            "error": str(e)
        }