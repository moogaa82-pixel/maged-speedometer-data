import json
import os
import time
import requests
from datetime import datetime

# سيرفرات متبادلة موثوقة لضمان التحميل حتى لو انقطع أحد السيرفرات
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

# الهيدر المخصص المعتمد لدى سيرفرات Overpass لمنع الحظر (429)
HEADERS = {
    'User-Agent': 'MagedSpeedometerUpdater/1.0 (https://github.com/maged-speedometer)',
    'Accept': 'application/json'
}

def query_overpass(ql_query):
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"Querying endpoint: {endpoint}...")
            response = requests.post(endpoint, data={'data': ql_query}, headers=HEADERS, timeout=180)
            if response.status_code == 200:
                data = response.json()
                if "elements" in data and len(data["elements"]) > 0:
                    return data
                elif "elements" in data:
                    print(f"Endpoint {endpoint} returned 0 elements, trying next mirror...")
            else:
                print(f"Endpoint {endpoint} failed with status code: {response.status_code}")
        except Exception as e:
            print(f"Error querying {endpoint}: {e}")
        time.sleep(3)
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

        geometry = {
            "type": "Point",
            "coordinates": [float(lon), float(lat)]
        }

        properties = {
            "@id": f"{el_type}/{el.get('id')}",
            "name": tags.get("name", tags.get("name:ar", tags.get("name:en", tags.get("ref", "")))),
            "brand": tags.get("brand", tags.get("operator", "")),
            "maxspeed": tags.get("maxspeed", tags.get("speed", "")),
            "highway": tags.get("highway", ""),
            "amenity": tags.get("amenity", ""),
            "traffic_calming": tags.get("traffic_calming", "")
        }

        clean_props = {k: v for k, v in properties.items() if v}
        clean_props["@id"] = properties["@id"]

        feature = {
            "type": "Feature",
            "id": properties["@id"],
            "properties": clean_props,
            "geometry": geometry
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features
    }

def fetch_radars():
    print("\n--- Fetching Radars for Egypt ---")
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="EG"]->.searchArea;
    (
      node["highway"="speed_camera"](area.searchArea);
      node["enforcement"="maxspeed"](area.searchArea);
      way["highway"="speed_camera"](area.searchArea);
      relation["highway"="speed_camera"](area.searchArea);
    );
    out center;
    """
    data = query_overpass(query)
    geojson = overpass_to_geojson(data)
    if len(geojson["features"]) > 0:
        with open("radars.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"✅ Successfully saved radars.geojson ({len(geojson['features'])} items)")
    else:
        print("⚠️ Radar query returned 0 items, preserving existing radars.geojson file!")

def fetch_speed_bumps():
    print("\n--- Fetching Speed Bumps for Egypt ---")
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="EG"]->.searchArea;
    (
      node["traffic_calming"](area.searchArea);
      node["highway"="speed_bump"](area.searchArea);
      way["traffic_calming"](area.searchArea);
      relation["traffic_calming"](area.searchArea);
    );
    out center;
    """
    data = query_overpass(query)
    geojson = overpass_to_geojson(data)
    if len(geojson["features"]) > 0:
        with open("speed_bumps.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"✅ Successfully saved speed_bumps.geojson ({len(geojson['features'])} items)")
    else:
        print("⚠️ Speed bumps query returned 0 items, preserving existing speed_bumps.geojson file!")

def fetch_fuel_stations():
    print("\n--- Fetching Fuel Stations for Egypt ---")
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="EG"]->.searchArea;
    (
      node["amenity"="fuel"](area.searchArea);
      way["amenity"="fuel"](area.searchArea);
      relation["amenity"="fuel"](area.searchArea);
    );
    out center;
    """
    data = query_overpass(query)
    geojson = overpass_to_geojson(data)
    if len(geojson["features"]) > 0:
        with open("fuel.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"✅ Successfully saved fuel.geojson ({len(geojson['features'])} items)")
    else:
        print("⚠️ Fuel stations query returned 0 items, preserving existing fuel.geojson file!")

def fetch_hospitals():
    print("\n--- Fetching Hospitals for Egypt ---")
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="EG"]->.searchArea;
    (
      node["amenity"="hospital"](area.searchArea);
      way["amenity"="hospital"](area.searchArea);
      relation["amenity"="hospital"](area.searchArea);
      node["healthcare"="hospital"](area.searchArea);
      way["healthcare"="hospital"](area.searchArea);
    );
    out center;
    """
    data = query_overpass(query)
    geojson = overpass_to_geojson(data)
    if len(geojson["features"]) > 0:
        with open("hospital.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"✅ Successfully saved hospital.geojson ({len(geojson['features'])} items)")
    else:
        print("⚠️ Hospitals query returned 0 items, preserving existing hospital.geojson file!")

def update_version_manifest():
    version = 1
    if os.path.exists("version.json"):
        try:
            with open("version.json", "r", encoding="utf-8") as f:
                vdata = json.load(f)
                version = vdata.get("version", 0) + 1
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
    print(f"Updated version.json to version {version}")

if __name__ == "__main__":
    fetch_radars()
    time.sleep(3)
    fetch_speed_bumps()
    time.sleep(3)
    fetch_fuel_stations()
    time.sleep(3)
    fetch_hospitals()
    time.sleep(1)
    update_version_manifest()
    print("\n🎉 All datasets update workflow finished successfully!")
