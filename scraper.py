import requests

URL = "https://dbysmgw.doa.gov.tr/dbys/v3/web/rvm/search?pageNumber=1&pageSize=100"

payload = {
    "lat": 37.21596145629883,
    "lon": 28.36799430847168,
    "distance": 2466,
    "userLat": 37.212301266949034,
    "userLon": 28.354810181393365
}


def siteyi_test_et():
    response = requests.post(URL, json=payload)

    data = response.json()

    print("=" * 50)
    print("Makine Sayısı:", len(data["rvmList"]))
    print("=" * 50)

    for makina in data["rvmList"]:

        print()
        print(makina["definition"]["name"])

        for kutu in makina["binList"]:

            durum = "UYGUN" if kutu["state"] else "DOLU"

            print(
                kutu["contentType"],
                kutu["level"],
                "%",
                durum
            )
