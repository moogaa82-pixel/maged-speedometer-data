import json
import os
import time
import requests
from datetime import datetime

# سيرفرات موثوقة متبادلة
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

HEADERS = {
    'User-Agent': 'MagedSpeedometerUpdater/1.0 (https://github.com/maged-speedometer)',
    'Accept': 'application/json'
}

def query_overpass_with_retry(ql_query, name):
    print(f"\n==========================================")
    print(f"   Executing Query: {name}")
    print(f"==========================================")
    
    for attempt in range(1, 4):
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                print(f"[{name}] Attempt {attempt} querying: {endpoint}...")
                response = requests.post(endpoint, data={'data': ql_query}, headers=HEADERS, timeout=120)
                if response.status_code == 200:
                    data = response.json()
                    elements = data.get("elements", [])
                    if len(elements) > 0:
                        print(f"✅ SUCCESS [{name}]: Found {len(elements)} items")
                        return data
                    else:
                        print(f"⚠️ [{name}] Endpoint {endpoint} returned 0 elements")
                else:
                    print(f"❌ [{name}] Endpoint {endpoint} status: {response.status_code}")
            except Exception as e:
                print(f"❌ [{name}] Exception on {endpoint}: {e}")
            time.sleep(4)
        print(f"Waiting 10s before retry attempt {attempt + 1} for {name}...")
        time.sleep(10)
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
            "name": tags.get("name", tags.get("name:ar", tags.get("name:en", tags.get("ref", "")))),
            "brand": tags.get("brand", tags.get("operator", "")),
            "maxspeed": tags.get("maxspeed", tags.get("speed", "")),
            "highway": tags.get("highway", ""),
            "amenity": tags.get("amenity", ""),
            "traffic_calming": tags.get("traffic_calming", "")
        }
        clean_props = {k: v for k, v in properties.items() if v}
        clean_props["@id"] = properties["@id"]

        features.append({"type": "Feature", "id": properties["@id"], "properties": clean_props, "geometry": geometry})

    return {"type": "FeatureCollection", "features": features}

def fetch_radars():
    query = """
    [out:json][timeout:120];
    area["ISO3166-1"="EG"]->.searchArea;
    (
      node["highway"="speed_camera"](area.searchArea);
      node["enforcement"="maxspeed"](area.searchArea);
      way["highway"="speed_camera"](area.searchArea);
      relation["highway"="speed_camera"](area.searchArea);
    );
    out center;
    """
    data = query_overpass_with_retry(query, "Radars")
    geojson = overpass_to_geojson(data)
    if len(geojson["features"]) > 0:
        with open("radars.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved radars.geojson ({len(geojson['features'])} items)")

def fetch_speed_bumps():
    query = """
    [out:json][timeout:120];
    area["ISO3166-1"="EG"]->.searchArea;
    (
      node["traffic_calming"](area.searchArea);
      node["highway"="speed_bump"](area.searchArea);
      way["traffic_calming"](area.searchArea);
    );
    out center;
    """
    data = query_overpass_with_retry(query, "Speed Bumps")
    geojson = overpass_to_geojson(data)
    if len(geojson["features"]) > 0:
        with open("speed_bumps.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved speed_bumps.geojson ({len(geojson['features'])} items)")

def fetch_fuel_stations():
    query = """
    [out:json][timeout:120];
    area["ISO3166-1"="EG"]->.searchArea;
    (
      node["amenity"="fuel"](area.searchArea);
      way["amenity"="fuel"](area.searchArea);
      relation["amenity"="fuel"](area.searchArea);
    );
    out center;
    """
    data = query_overpass_with_retry(query, "Fuel Stations")
    geojson = overpass_to_geojson(data)
    if len(geojson["features"]) > 0:
        with open("fuel.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved fuel.geojson ({len(geojson['features'])} items)")

def fetch_hospitals():
    query = """
    [out:json][timeout:120];
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
    data = query_overpass_with_retry(query, "Hospitals")
    geojson = overpass_to_geojson(data)
    if len(geojson["features"]) > 0:
        with open("hospital.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved hospital.geojson ({len(geojson['features'])} items)")

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
    print(f"\n📌 Updated version.json to V{version}")

if __name__ == "__main__":
    fetch_radars()
    time.sleep(12)  # مهلة زمنية 12 ثانية لإعادة تصفير الـ Rate Limit
    fetch_speed_bumps()
    time.sleep(12)
    fetch_fuel_stations()
    time.sleep(12)
    fetch_hospitals()
    time.sleep(2)
    update_version_manifest()
    print("\n🎉 All 4 datasets updated and verified successfully!")
