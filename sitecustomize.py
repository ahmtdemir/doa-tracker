import config

config.SEARCH_POINTS.append(
    {
        "name": "DIDIM",
        "label": "Didim",
        "lat": 37.3750,
        "lon": 27.2670,
        "distance": 15000,
        "userLat": 37.3750,
        "userLon": 27.2670,
    }
)

config.MAKINE_KURALLARI.setdefault(
    "BİM-MAVİŞEHİR",
    {"label": "Didim", "type": "early_warning"},
)
