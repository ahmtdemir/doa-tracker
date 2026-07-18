API_URL = (
    "https://dbysmgw.doa.gov.tr/"
    "dbys/v3/web/rvm/search?pageNumber=1&pageSize=100"
)

SEARCH_POINTS = [
    {
        "name": "MENTESE",
        "label": "Muğla Merkez",
        "lat": 37.21596145629883,
        "lon": 28.36799430847168,
        "distance": 15000,
        "userLat": 37.212301266949034,
        "userLon": 28.354810181393365,
    },
    {
        "name": "ULA",
        "label": "Ula",
        "lat": 37.1030,
        "lon": 28.4160,
        "distance": 15000,
        "userLat": 37.1030,
        "userLon": 28.4160,
    },
    {
        "name": "YATAGAN",
        "label": "Yatağan",
        "lat": 37.3400,
        "lon": 28.1400,
        "distance": 15000,
        "userLat": 37.3400,
        "userLon": 28.1400,
    },
]

MAKINE_KURALLARI = {
    "Q681 BİM NERGİS": {
        "label": "Muğla Merkez",
        "type": "target",
    },
    "MİGROS MUĞLA": {
        "label": "Muğla Merkez",
        "type": "target",
    },
    "BİM-AYDINLIKEVLER": {
        "label": "Milas",
        "type": "early_warning",
    },
}

OTOMATIK_ERKEN_UYARI_BOLGELERI = {
    "ULA",
    "YATAGAN",
}

TAKIP_KUTULARI = {
    "pet",
    "glass",
    "can",
    "aluminum",
}
