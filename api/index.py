import os
import time
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from redis import Redis

app = Flask(__name__)
CORS(app)

# --- PERMANENT STORAGE ENGINE ---
# Vercel Serverless क्लस्टर स्लीप मोड में जाने पर भी डेटा सुरक्षित रखने के लिए फ़ाइल बैकअप पाथ
LOCAL_FILE_DB = "/tmp/shayan_keys_vault.json"

def load_local_vault():
    if os.path.exists(LOCAL_FILE_DB):
        try:
            with open(LOCAL_FILE_DB, 'r') as f:
                return json.load(f)
        except: return {}
    return {}

def save_local_vault(data):
    try:
        with open(LOCAL_FILE_DB, 'w') as f:
            json.dump(data, f)
    except: pass

KV_URL = os.environ.get("KV_URL", "")
if KV_URL.startswith("redis://") or KV_URL.startswith("rediss://"):
    db = Redis.from_url(KV_URL, decode_responses=True)
    is_redis = True
else:
    is_redis = False
    class MockRedisEngine:
        def __init__(self):
            self.data = load_local_vault()
        def get(self, k): return self.data.get(k)
        def set(self, k, v): 
            self.data[k] = str(v)
            save_local_vault(self.data)
            return True
        def hgetall(self, k): return self.data.get(k, {})
        def hset(self, k, mapping=None):
            if k not in self.data: self.data[k] = {}
            if mapping: self.data[k].update(mapping)
            save_local_vault(self.data)
            return len(mapping)
        def del_key(self, k):
            if k in self.data: 
                del self.data[k]
                save_local_vault(self.data)
                return 1
            return 0
        def keys(self, p): 
            prefix = p.replace('*', '')
            return [k for k in self.data.keys() if k.startswith(prefix)]
        def lpush(self, k, v):
            if k not in self.data: self.data[k] = []
            self.data[k].insert(0, v)
            save_local_vault(self.data)
        def lrange(self, k, s, e): return self.data.get(k, [])[:50]
    db = MockRedisEngine()

# Master Source Core Links Configuration
MASTER_KEY = "vernex-6a9dc4fdd5923c40b0aba27bf1e39e3f"
TOOLS_CONFIG = {
    "number": f"https://ft-osint-api.duckdns.org/api/number?key={MASTER_KEY}",
    "vehicle": f"https://ft-osint-api.duckdns.org/api/vehicle?key={MASTER_KEY}",
    "aadhar": f"https://ft-osint-api.duckdns.org/api/aadhar?key={MASTER_KEY}",
    "family": f"https://ft-osint-api.duckdns.org/api/adharfamily?key={MASTER_KEY}",
    "insta": f"https://ft-osint-api.duckdns.org/api/insta?key={MASTER_KEY}"
}

def clean_branding_data(data):
    data_str = json.dumps(data)
    data_str = data_str.replace("@ftgamer2", "shayan_explorer").replace("@FTgamer2", "shayan_explorer")
    data_str = data_str.replace("FTgamer2", "shayan_explorer").replace("ftgamer2", "shayan_explorer")
    data_str = data_str.replace("https://t.me/lynx_api", "https://t.me/shayan_explorer_channel")
    data_str = data_str.replace("https://t.me/FTgamer2", "https://t.me/shayan_explorer_channel")
    
    cleaned = json.loads(data_str)
    if isinstance(cleaned, dict):
        cleaned["by"] = "shayan_explorer"
        cleaned["channel"] = "https://t.me/shayan_explorer_channel"
    return cleaned

@app.route('/api/admin/keys', methods=['GET', 'POST'])
def manage_keys():
    if request.method == 'POST':
        data = request.json or {}
        custom_key = data.get('key')
        if not custom_key: return jsonify({"error": "Key parameter required"}), 400
        
        db.hset(f"apikey:{custom_key}", mapping={
            "name": data.get('name', 'Client Reference'),
            "key": custom_key,
            "price": float(data.get('price', 0) or 0),
            "daily_limit": int(data.get('daily_limit', 1000)),
            "expire_date": data.get('expire_date', '2026-12-31'),
            "status": data.get('status', 'on'),
            "allow_number": "true" if str(data.get('allow_number')).lower() == "true" else "false",
            "allow_vehicle": "true" if str(data.get('allow_vehicle')).lower() == "true" else "false",
            "allow_aadhar": "true" if str(data.get('allow_aadhar')).lower() == "true" else "false",
            "allow_family": "true" if str(data.get('allow_family')).lower() == "true" else "false",
            "allow_insta": "true" if str(data.get('allow_insta')).lower() == "true" else "false"
        })
        return jsonify({"success": True})
        
    all_keys = []
    for k in db.keys("apikey:*"):
        val = db.hgetall(k)
        if val: all_keys.append(val)
    return jsonify({"keys": all_keys})

@app.route('/api/admin/keys/delete', methods=['POST'])
def delete_key():
    data = request.json or {}
    target_key = data.get('key')
    if is_redis:
        db.delete(f"apikey:{target_key}")
    else:
        db.del_key(f"apikey:{target_key}")
    return jsonify({"success": True, "message": "Cluster Purged Successfully"})

@app.route('/api/admin/toggle', methods=['POST'])
def toggle_key():
    data = request.json or {}
    key_name = data.get('key')
    current_status = data.get('status', 'on')
    new_status = 'off' if current_status == 'on' else 'on'
    db.hset(f"apikey:{key_name}", mapping={"status": new_status})
    return jsonify({"success": True, "new_status": new_status})

@app.route('/api/admin/history', methods=['GET'])
def get_global_history():
    logs = db.lrange("api:history", 0, 49) or []
    return jsonify({"history": [json.loads(x) for x in logs]})

def execute_proxy(tool_name, query_param, tracking_label):
    client_key = request.args.get('key')
    lookup_input = request.args.get(query_param)
    if not lookup_input: return jsonify({"error": f"Missing parameter '{query_param}'"}), 400
    
    key_meta = db.hgetall(f"apikey:{client_key}")
    if not key_meta: return jsonify({"error": "Unauthorized API Key"}), 403
    if key_meta.get("status", "on") != "on": return jsonify({"error": "Key Suspended"}), 403
    
    # टाइमर चेकिंग सीधे सर्वर साइड पर बैकग्राउंड ऑपरेशन्स के लिए
    current_date = time.strftime("%Y-%m-%d")
    if current_date > key_meta.get("expire_date", "2026-12-31"):
        if is_redis: db.delete(f"apikey:{client_key}")
        else: db.del_key(f"apikey:{client_key}")
        return jsonify({"error": "Key Expired automatically in background"}), 403
        
    if key_meta.get(f"allow_{tool_name}", "false") != "true": return jsonify({"error": "Access Denied"}), 403
    
    try:
        target_url = f"{TOOLS_CONFIG[tool_name]}&{query_param}={lookup_input}"
        response = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        upstream_data = clean_branding_data(response.json() if response.status_code == 200 else {"raw": response.text})
    except Exception as e:
        return jsonify({"error": "Upstream timeout", "details": str(e)}), 502
        
    log_query = "[Masked]" if "aadhar" in tool_name else lookup_input
    db.lpush("api:history", json.dumps({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "key_used": client_key,
        "client_name": key_meta.get("name"),
        "type": tracking_label,
        "query": log_query,
        "status_code": response.status_code
    }))
    return jsonify(upstream_data)

@app.route('/api/number', methods=['GET'])
def lookup_num(): return execute_proxy("number", "num", "NUMBER LOOKUP")

@app.route('/api/vehicle', methods=['GET'])
def lookup_veh(): return execute_proxy("vehicle", "vehicle", "VEHICLE LOOKUP")

@app.route('/api/aadhar', methods=['GET'])
def lookup_adr(): return execute_proxy("aadhar", "num", "AADHAR LOOKUP")

@app.route('/api/adharfamily', methods=['GET'])
def lookup_fam(): return execute_proxy("family", "num", "FAMILY LOOKUP")

@app.route('/api/insta', methods=['GET'])
def lookup_ins(): return execute_proxy("insta", "username", "INSTAGRAM TRACE")

def handler(request):
    return app(request)

if __name__ == '__main__':
    app.run(debug=True)
