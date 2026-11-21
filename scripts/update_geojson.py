import json
import os
import time
import requests
from datetime import datetime

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

HEADERS = {
    'User-Agent': 'MagedSpeedometerUpdater/1.0 (https://github.com/maged-speedometer)',
    'Accept': 'application/json'
}

def get_existing_file_path(filename):
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", filename))
    assets_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets", filename))
    if os.path.exists(root_path):
        return root_path
    elif os.path.exists(assets_path):
        return assets_path
    return root_path

def save_geojson_file(filename, data):
    paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", filename)),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets", filename))
    ]
    for p in paths:
        if os.path.exists(os.path.dirname(p)):
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"💾 Saved dataset to: {p}")
            except Exception as e:
                print(f"⚠️ Could not write to {p}: {e}")

def load_existing_custom_features(filename):
    file_path = get_existing_file_path(filename)
    custom_features = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                features = data.get("features", [])
                for feat in features:
                    f_id = str(feat.get("id", ""))
                    prop_id = str(feat.get("properties", {}).get("@id", ""))
                    if "custom_bump_" in f_id or "custom_bump_" in prop_id or "custom_radar_" in f_id or "custom_radar_" in prop_id:
                        custom_features.append(feat)
        except Exception as e:
            print(f"⚠️ Could not read existing custom features from {filename}: {e}")
    return custom_features

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
        existing_custom = load_existing_custom_features("radars.geojson")
        existing_ids = {f.get("id", "") for f in geojson["features"]}
        for cf in existing_custom:
            if cf.get("id", "") not in existing_ids:
                geojson["features"].append(cf)
                existing_ids.add(cf.get("id", ""))
        save_geojson_file("radars.geojson", geojson)
        print(f"🎉 Saved radars.geojson ({len(geojson['features'])} items, including {len(existing_custom)} crowdsourced)")

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
        existing_custom = load_existing_custom_features("speed_bumps.geojson")
        existing_ids = {f.get("id", "") for f in geojson["features"]}
        for cf in existing_custom:
            if cf.get("id", "") not in existing_ids:
                geojson["features"].append(cf)
                existing_ids.add(cf.get("id", ""))
        save_geojson_file("speed_bumps.geojson", geojson)
        print(f"🎉 Saved speed_bumps.geojson ({len(geojson['features'])} items, including {len(existing_custom)} crowdsourced)")

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
        save_geojson_file("fuel.geojson", geojson)
        print(f"🎉 Saved fuel.geojson ({len(geojson['features'])} items)")

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
        save_geojson_file("hospital.geojson", geojson)
        print(f"🎉 Saved hospital.geojson ({len(geojson['features'])} items)")

def bump_semantic_version(v_str):
    v_clean = str(v_str).lstrip("vV")
    parts = v_clean.split(".")
    if len(parts) == 3:
        try:
            return f"v{int(parts[0])}.{int(parts[1])}.{int(parts[2]) + 1}"
        except ValueError:
            pass
    elif len(parts) == 2:
        try:
            return f"v{int(parts[0])}.{int(parts[1])}.1"
        except ValueError:
            pass
    return f"v1.0.{int(v_clean) + 1}" if v_clean.isdigit() else "v1.0.1"

def update_version_manifest():
    file_path = get_existing_file_path("version.json")
    old_version_str = "v1.0.0"
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                vdata = json.load(f)
                old_version_str = str(vdata.get("version", "v1.0.0"))
        except Exception:
            old_version_str = "v1.0.0"

    new_version_str = bump_semantic_version(old_version_str)

    manifest = {
        "version": new_version_str,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "datasets": {
            "radars": "radars.geojson",
            "speed_bumps": "speed_bumps.geojson",
            "fuel": "fuel.geojson",
            "hospitals": "hospital.geojson"
        }
    }
    save_geojson_file("version.json", manifest)
    print(f"\n🚀 Updated version.json: {old_version_str} -> {new_version_str}")

if __name__ == "__main__":
    fetch_radars()
    time.sleep(12)
    fetch_speed_bumps()
    time.sleep(12)
    fetch_fuel_stations()
    time.sleep(12)
    fetch_hospitals()
    time.sleep(2)
    update_version_manifest()
    print("\n🎉 All GeoJSON datasets updated and verified successfully!")
