import json
import urllib.request
import os

FIREBASE_DB_URLS = [
    "https://smart-drive-assist-6aecd-default-rtdb.firebaseio.com/.json",
    "https://smart-drive-assist-6aecd-default-rtdb.europe-west1.firebasedatabase.app/.json"
]

def get_existing_geojson_path(filename):
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

def delete_firebase_node(node_path):
    base_url = "https://smart-drive-assist-6aecd-default-rtdb.firebaseio.com"
    url = f"{base_url}/{node_path}.json"
    try:
        req = urllib.request.Request(url, method='DELETE', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in (200, 204):
                print(f"🔥 Cloud Purge Success: Deleted {node_path}")
    except Exception as e:
        print(f"⚠️ Could not delete {node_path} from Firebase: {e}")

BLACKLIST_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "blacklisted_nodes.json")

def load_blacklist():
    path = os.path.abspath(BLACKLIST_FILE_PATH)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_blacklist(blacklisted_ids):
    path = os.path.abspath(BLACKLIST_FILE_PATH)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted(list(blacklisted_ids)), f, ensure_ascii=False, indent=2)
        print(f"🚫 Permanent Blacklist updated: {len(blacklisted_ids)} items in {path}")
    except Exception as e:
        print(f"⚠️ Could not save blacklist to {path}: {e}")

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

def sync_crowdsourced_bumps(fb_data):
    print("\n--- Syncing Speed Bumps Dataset ---")
    pending_bumps = fb_data.get("pending_bumps", {})
    approved_bumps = fb_data.get("approved_bumps", {})

    rejected_ids = set()
    approved_to_add = {}

    import time
    fourteen_days_ms = 14 * 24 * 60 * 60 * 1000
    now_ms = int(time.time() * 1000)

    blacklisted_ids = load_blacklist()

    for b_id, b_info in pending_bumps.items():
        if isinstance(b_info, dict):
            status = b_info.get("status", "PENDING")
            ts = b_info.get("timestamp", now_ms)
            if status == "REJECTED" or (status == "PENDING" and (now_ms - ts > fourteen_days_ms)):
                rejected_ids.add(b_id)
                blacklisted_ids.add(b_id)
                blacklisted_ids.add(f"node/{b_id}")
            elif status == "APPROVED":
                approved_to_add[b_id] = b_info

    for b_id, b_info in approved_bumps.items():
        if isinstance(b_info, dict):
            approved_to_add[b_id] = b_info

    geojson_file_path = get_existing_geojson_path("speed_bumps.geojson")
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

        if f_id in rejected_ids or prop_id in rejected_ids or f_id in blacklisted_ids or prop_id in blacklisted_ids:
            print(f"🗑️ Removing rejected/blacklisted bump: {f_id or prop_id}")
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
    save_geojson_file("speed_bumps.geojson", geojson)
    save_blacklist(blacklisted_ids)

    # Auto-Purge processed items from Firebase Realtime DB
    for r_id in rejected_ids:
        delete_firebase_node(f"pending_bumps/{r_id}")
    for b_id in approved_to_add.keys():
        delete_firebase_node(f"approved_bumps/{b_id}")
        delete_firebase_node(f"pending_bumps/{b_id}")

    final_count = len(filtered_features)
    print(f"🎉 Bumps Sync Complete! Features count: {initial_count} -> {final_count} (+{added_count} added).")

def sync_crowdsourced_radars(fb_data):
    print("\n--- Syncing Speed Radars Dataset ---")
    pending_radars = fb_data.get("pending_radars", {})
    approved_radars = fb_data.get("approved_radars", {})
    rejected_radars = fb_data.get("rejected_radars", {})

    rejected_ids = set(rejected_radars.keys()) if isinstance(rejected_radars, dict) else set()
    approved_to_add = {}

    blacklisted_ids = load_blacklist()

    for r_id, r_info in pending_radars.items():
        if isinstance(r_info, dict):
            status = r_info.get("status", "PENDING")
            ts = r_info.get("timestamp", now_ms)
            if status == "REJECTED" or (status == "PENDING" and (now_ms - ts > fourteen_days_ms)):
                rejected_ids.add(r_id)
                blacklisted_ids.add(r_id)
                blacklisted_ids.add(f"node/{r_id}")
            elif status == "APPROVED":
                approved_to_add[r_id] = r_info

    for r_id, r_info in approved_radars.items():
        if isinstance(r_info, dict):
            approved_to_add[r_id] = r_info

    geojson_file_path = get_existing_geojson_path("radars.geojson")
    if not os.path.exists(geojson_file_path):
        print(f"❌ Radars GeoJSON file not found at: {geojson_file_path}")
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

        if f_id in rejected_ids or prop_id in rejected_ids or f_id in blacklisted_ids or prop_id in blacklisted_ids:
            print(f"🗑️ Removing rejected/blacklisted radar: {f_id or prop_id}")
            continue
        filtered_features.append(f)

    existing_ids = {f.get("id", "") for f in filtered_features}
    existing_ids.update({f.get("properties", {}).get("@id", "") for f in filtered_features})

    added_count = 0
    for r_id, r_info in approved_to_add.items():
        if r_id in existing_ids:
            continue

        lat = r_info.get("lat")
        lng = r_info.get("lng")
        speed = r_info.get("speed", 90)
        name = r_info.get("name", "رادار رصد سرعة مؤكد")
        if lat is None or lng is None:
            continue

        new_feature = {
            "type": "Feature",
            "properties": {
                "@id": f"node/{r_id}",
                "highway": "speed_camera",
                "maxspeed": str(speed),
                "name": name
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "id": f"node/{r_id}"
        }
        filtered_features.append(new_feature)
        existing_ids.add(r_id)
        added_count += 1
        print(f"➕ Added approved radar: {r_id} at ({lat}, {lng}) speed {speed}")

    geojson["features"] = filtered_features
    save_geojson_file("radars.geojson", geojson)
    save_blacklist(blacklisted_ids)

    # Auto-Purge processed items from Firebase Realtime DB
    for r_id in rejected_ids:
        delete_firebase_node(f"pending_radars/{r_id}")
        delete_firebase_node(f"rejected_radars/{r_id}")
    for r_id in approved_to_add.keys():
        delete_firebase_node(f"approved_radars/{r_id}")
        delete_firebase_node(f"pending_radars/{r_id}")

    final_count = len(filtered_features)
    print(f"🎉 Radars Sync Complete! Features count: {initial_count} -> {final_count} (+{added_count} added).")

def main():
    print("🚀 Starting Firebase to GitHub Auto-Sync Bridge for Bumps & Radars...")
    fb_data = fetch_firebase_data()
    if not fb_data:
        print("ℹ️ No new data or empty Firebase database. Nothing to sync.")
        return

    sync_crowdsourced_bumps(fb_data)
    sync_crowdsourced_radars(fb_data)

if __name__ == "__main__":
    main()
