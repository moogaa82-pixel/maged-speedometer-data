import json
import os
import time
import requests
from datetime import datetime

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
EGYPT_BBOX = "22.0,24.5,31.8,37.0"

def query_overpass(ql_query):
    try:
        response = requests.post(OVERPASS_URL, data={'data': ql_query}, timeout=120)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed with status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error querying Overpass API: {e}")
        return None

def overpass_to_geojson(overpass_data):
    features = []
    if not overpass_data or "elements" not in overpass_data:
        return {"type": "FeatureCollection", "features": []}

    for el in overpass_data["elements"]:
        el_type = el.get("type")
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        
        if lat is None or lon is None:
            continue

        geometry = {"type": "Point", "coordinates": [float(lon), float(lat)]}
        properties = {
            "@id": f"{el_type}/{el.get('id')}",
            "name": tags.get("name", tags.get("name:ar", tags.get("name:en", ""))),
            "brand": tags.get("brand", tags.get("operator", "")),
            "maxspeed": tags.get("maxspeed", ""),
            "amenity": tags.get("amenity", ""),
            "highway": tags.get("highway", ""),
            "traffic_calming": tags.get("traffic_calming", "")
        }
        clean_props = {k: v for k, v in properties.items() if v}
        clean_props["@id"] = properties["@id"]

        features.append({"type": "Feature", "id": properties["@id"], "properties": clean_props, "geometry": geometry})

    return {"type": "FeatureCollection", "features": features}

def fetch_radars():
    print("Fetching Radars...")
    query = f'[out:json][timeout:120];(node["highway"="speed_camera"]({EGYPT_BBOX}););out body;'
    data = query_overpass(query)
    geojson = overpass_to_geojson(data)
    with open("radars.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

def fetch_speed_bumps():
    print("Fetching Speed Bumps...")
    query = f'[out:json][timeout:120];(node["traffic_calming"~"bump|hump|table"]({EGYPT_BBOX}););out body;'
    data = query_overpass(query)
    geojson = overpass_to_geojson(data)
    with open("speed_bumps.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

def fetch_fuel_stations():
    print("Fetching Fuel Stations...")
    query = f'[out:json][timeout:120];(node["amenity"="fuel"]({EGYPT_BBOX});way["amenity"="fuel"]({EGYPT_BBOX});relation["amenity"="fuel"]({EGYPT_BBOX}););out center;'
    data = query_overpass(query)
    geojson = overpass_to_geojson(data)
    with open("fuel.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

def fetch_hospitals():
    print("Fetching Hospitals...")
    query = f'[out:json][timeout:120];(node["amenity"="hospital"]({EGYPT_BBOX});way["amenity"="hospital"]({EGYPT_BBOX});relation["amenity"="hospital"]({EGYPT_BBOX});node["healthcare"="hospital"]({EGYPT_BBOX});way["healthcare"="hospital"]({EGYPT_BBOX}););out center;'
    data = query_overpass(query)
    geojson = overpass_to_geojson(data)
    with open("hospital.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

def update_version_manifest():
    version = 1
    if os.path.exists("version.json"):
        try:
            with open("version.json", "r", encoding="utf-8") as f:
                version = json.load(f).get("version", 0) + 1
        except Exception:
            version = 1

    manifest = {
        "version": version,
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "datasets": {
            "radars": "radars.geojson",
            "speed_bumps": "speed_bumps.geojson",
            "fuel": "fuel.geojson",
            "hospitals": "hospital.geojson"
        }
    }
    with open("version.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_radars()
    time.sleep(2)
    fetch_speed_bumps()
    time.sleep(2)
    fetch_fuel_stations()
    time.sleep(2)
    fetch_hospitals()
    time.sleep(1)
    update_version_manifest()
    print("All datasets updated successfully!")
