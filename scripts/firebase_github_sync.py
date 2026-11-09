import json
import urllib.request
import os

FIREBASE_DB_URLS = [
    "https://smart-drive-assist-6aecd-default-rtdb.firebaseio.com/.json",
    "https://smart-drive-assist-6aecd-default-rtdb.europe-west1.firebasedatabase.app/.json"
]

GEOJSON_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets", "speed_bumps.geojson")

def fetch_firebase_data():
    for url in FIREBASE_DB_URLS:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data_str = response.read().decode('utf-8')
                    if data_str and data_str != "null":
                        print(f"✅ Successfully fetched data from Firebase: {url}")
                        return json.loads(data_str)
        except Exception as e:
            print(f"⚠️ Could not reach {url}: {e}")
    return {}

def sync_crowdsourced_bumps():
    print("🚀 Starting Firebase to GitHub Auto-Sync Bridge...")
    
    fb_data = fetch_firebase_data()
    if not fb_data:
        print("ℹ️ No new data or empty Firebase database. Nothing to sync.")
        return

    pending_bumps = fb_data.get("pending_bumps", {})
    approved_bumps = fb_data.get("approved_bumps", {})

    rejected_ids = set()
    approved_to_add = {}

    for b_id, b_info in pending_bumps.items():
        if isinstance(b_info, dict):
            status = b_info.get("status", "PENDING")
            if status == "REJECTED":
                rejected_ids.add(b_id)
            elif status == "APPROVED":
                approved_to_add[b_id] = b_info

    for b_id, b_info in approved_bumps.items():
        if isinstance(b_info, dict):
            approved_to_add[b_id] = b_info

    print(f"📊 Summary from Firebase: {len(approved_to_add)} approved bumps, {len(rejected_ids)} rejected bumps.")

    geojson_file_path = os.path.abspath(GEOJSON_PATH)
    if not os.path.exists(geojson_file_path):
        print(f"❌ GeoJSON file not found at: {geojson_file_path}")
        return

    with open(geojson_file_path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    features = geojson.get("features", [])
    initial_count = len(features)

    filtered_features = []
    for f in features:
        f_id = f.get("id", "")
        f_props = f.get("properties", {})
        prop_id = f_props.get("@id", "")
        
        if f_id in rejected_ids or prop_id in rejected_ids:
            print(f"🗑️ Removing rejected bump: {f_id}")
            continue
        filtered_features.append(f)

    existing_ids = {f.get("id", "") for f in filtered_features}
    existing_ids.update({f.get("properties", {}).get("@id", "") for f in filtered_features})

    added_count = 0
    for b_id, b_info in approved_to_add.items():
        if b_id in existing_ids:
            continue
        
        lat = b_info.get("lat")
        lng = b_info.get("lng")
        if lat is None or lng is None:
            continue

        new_feature = {
            "type": "Feature",
            "properties": {
                "@id": f"node/{b_id}",
                "traffic_calming": "bump",
                "name": "مطب مخصص مؤكد"
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "id": f"node/{b_id}"
        }
        filtered_features.append(new_feature)
        existing_ids.add(b_id)
        added_count += 1
        print(f"➕ Added approved bump: {b_id} at ({lat}, {lng})")

    geojson["features"] = filtered_features
    with open(geojson_file_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    final_count = len(filtered_features)
    print(f"🎉 Sync Complete! Features count: {initial_count} -> {final_count} (+{added_count} added).")

if __name__ == "__main__":
    sync_crowdsourced_bumps()
