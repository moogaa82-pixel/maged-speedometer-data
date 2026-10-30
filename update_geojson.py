import json
import os
import time
import requests
from datetime import datetime

# سيرفرات متبادلة لضمان عدم الفشل أثناء التحميل
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

# حد حدود مصر الجغرافية (South, West, North, East)
EGYPT_BBOX = "21.8,24.5,32.0,37.0"

def query_overpass(ql_query):
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"Querying endpoint: {endpoint}...")
            response = requests.post(endpoint, data={'data': ql_query}, timeout=120)
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
        time.sleep(2)
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
    print("\n--- Fetching Radars ---")
    query = f"""
    [out:json][timeout:180];
    (
      node["highway"="speed_camera"]({EGYPT_BBOX});
      way["highway"="speed_camera"]({EGYPT_BBOX});
      relation["highway"="speed_camera"]({EGYPT_BBOX});
      node["enforcement"="maxspeed"]({EGYPT_BBOX});
      way["enforcement"="maxspeed"]({EGYPT_BBOX});
      relation["enforcement"="maxspeed"]({EGYPT_BBOX});
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
        print("⚠️ Warning: Radar query returned 0 items, keeping existing radars.geojson file!")

def fetch_speed_bumps():
    print("\n--- Fetching Speed Bumps ---")
    query = f"""
    [out:json][timeout:180];
    (
      node["traffic_calming"~"bump|hump|table"]({EGYPT_BBOX});
      way["traffic_calming"~"bump|hump|table"]({EGYPT_BBOX});
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
        print("⚠️ Warning: Speed bumps query returned 0 items, keeping existing speed_bumps.geojson file!")

def fetch_fuel_stations():
    print("\n--- Fetching Fuel Stations ---")
    query = f"""
    [out:json][timeout:180];
    (
      node["amenity"="fuel"]({EGYPT_BBOX});
      way["amenity"="fuel"]({EGYPT_BBOX});
      relation["amenity"="fuel"]({EGYPT_BBOX});
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
        print("⚠️ Warning: Fuel stations query returned 0 items, keeping existing fuel.geojson file!")

def fetch_hospitals():
    print("\n--- Fetching Hospitals ---")
    query = f"""
    [out:json][timeout:180];
    (
      node["amenity"="hospital"]({EGYPT_BBOX});
      way["amenity"="hospital"]({EGYPT_BBOX});
      relation["amenity"="hospital"]({EGYPT_BBOX});
      node["healthcare"="hospital"]({EGYPT_BBOX});
      way["healthcare"="hospital"]({EGYPT_BBOX});
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
        print("⚠️ Warning: Hospitals query returned 0 items, keeping existing hospital.geojson file!")

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
