import os
import time
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from redis import Redis

app = Flask(__name__)
CORS(app)

# Connect to Vercel KV Redis using Environment Variables
KV_URL = os.environ.get("KV_URL", "")
if KV_URL.startswith("redis://") or KV_URL.startswith("rediss://"):
    db = Redis.from_url(KV_URL, decode_responses=True)
else:
    # Fallback local mock dictionary if KV is not yet linked
    class MockRedis:
        def __init__(self): self.data = {}
        def get(self, k): return self.data.get(k)
        def set(self, k, v): self.data[k] = str(v); return True
        def hgetall(self, k): return self.data.get(k, {})
        def hset(self, k, mapping=None): 
            if k not in self.data: self.data[k] = {}
            if mapping: self.data[k].update(mapping)
            return len(mapping)
        def keys(self, p): return [k for k in self.data.keys() if k.startswith(p.replace('*',''))]
        def lpush(self, k, v):
            if k not in self.data: self.data[k] = []
            self.data[k].insert(0, v)
        def lrange(self, k, s, e): return self.data.get(k, [])[:10]
    db = MockRedis()

# Your main target API key configuration
TARGET_API_BASE = "https://ft-osint-api.duckdns.org/api/number?key=vernex-6a9dc4fdd5923c40b0aba27bf1e39e3f"

# Enhanced branding deep-cleaner to wipe out the old credentials completely
def clean_branding_data(data):
    # Convert data dictionary to a raw string for full find-and-replace masking
    data_str = json.dumps(data)
    
    # Clean the author fields (handles case sensitivity variations)
    data_str = data_str.replace("@ftgamer2", "Vernex")
    data_str = data_str.replace("@FTgamer2", "Vernex")
    data_str = data_str.replace("FTgamer2", "Vernex")
    data_str = data_str.replace("ftgamer2", "Vernex")
    
    # Wipe out the old channel link and clean up Telegram mentions
    data_str = data_str.replace("https://t.me/lynx_api", "https://t.me/vernex_api")
    data_str = data_str.replace("t.me/lynx_api", "t.me/vernex_api")
    data_str = data_str.replace("https://t.me/FTgamer2", "https://t.me/vernex_api")
    
    # Parse back into a structural Python dictionary
    cleaned_dict = json.loads(data_str)
    
    # Double check assurance: explicitly force the "by" key if present in the root layer
    if isinstance(cleaned_dict, dict):
        if "by" in cleaned_dict:
            cleaned_dict["by"] = "Vernex"
        if "channel" in cleaned_dict and "lynx_api" in str(cleaned_dict["channel"]):
            cleaned_dict["channel"] = "https://t.me/vernex_api"
            
    return cleaned_dict

# --- MANAGEMENT ENDPOINTS ---

@app.route('/api/admin/keys', methods=['GET', 'POST'])
def manage_keys():
    if request.method == 'POST':
        data = request.json or {}
        name = data.get('name', 'Unnamed Client')
        custom_key = data.get('key', f"custom-{int(time.time())}")
        daily_limit = int(data.get('daily_limit', 100))
        expire_date = data.get('expire_date', '2030-12-31')
        
        db.hset(f"apikey:{custom_key}", mapping={
            "name": name,
            "key": custom_key,
            "daily_limit": daily_limit,
            "expire_date": expire_date,
            "status": "on"
        })
        return jsonify({"success": True, "message": f"Key '{custom_key}' deployed successfully."})
    
    all_keys = []
    keys_in_db = db.keys("apikey:*")
    for k in keys_in_db:
        all_keys.append(db.hgetall(k))
    return jsonify({"keys": all_keys})

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


# --- THE CLIENT PROXY ENDPOINT ---

@app.route('/api/number', methods=['GET'])
def proxy_number_lookup():
    client_key = request.args.get('key')
    phone_number = request.args.get('num')
    
    if not client_key or not phone_number:
        return jsonify({"error": "Missing parameters 'key' or 'num'"}), 400
        
    # 1. Check if the API Key exists in KV Storage
    key_meta = db.hgetall(f"apikey:{client_key}")
    if not key_meta:
        return jsonify({"error": "Unauthorized: Invalid API Key"}), 403
        
    # 2. Check Switch Status (Master ON/OFF switch)
    if key_meta.get("status", "on") != "on":
        return jsonify({"error": "Forbidden: This API Key has been suspended"}), 403
        
    # 3. Check Expiration Date
    current_date = time.strftime("%Y-%m-%d")
    if current_date > key_meta.get("expire_date", "2030-12-31"):
        return jsonify({"error": f"Expired: Key expired on {key_meta.get('expire_date')}"}), 403
        
    # 4. Check Daily Usage Limit counter
    usage_key = f"usage:{client_key}:{current_date}"
    current_usage = int(db.get(usage_key) or 0)
    limit = int(key_meta.get("daily_limit", 100))
    
    if current_usage >= limit:
        return jsonify({"error": f"Rate Limit Exceeded: Daily capacity of {limit} reached"}), 429
        
    # 5. Route to Target Infrastructure
    try:
        upstream_url = f"{TARGET_API_BASE}&num={phone_number}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(upstream_url, headers=headers, timeout=12)
        
        # Safe JSON parse fallback if upstream sends plaintext/HTML errors
        try:
            upstream_data = response.json()
            # Run the deep-cleaning operation
            upstream_data = clean_branding_data(upstream_data)
        except Exception:
            # Fallback string manipulation if response isn't formatted properly
            raw_cleaned = response.text.replace("@ftgamer2", "Vernex").replace("@FTgamer2", "Vernex")
            raw_cleaned = raw_cleaned.replace("https://t.me/lynx_api", "https://t.me/vernex_api")
            upstream_data = {"raw_response": raw_cleaned, "status_code": response.status_code}
            
    except Exception as e:
        return jsonify({
            "error": "Target server infrastructure timeout", 
            "details": str(e)
        }), 502

    # Increment usage counter safely
    db.set(usage_key, current_usage + 1)
    
    # 6. Log transaction history trace
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "key_used": client_key,
        "client_name": key_meta.get("name"),
        "queried_num": phone_number,
        "status_code": response.status_code
    }
    db.lpush("api:history", json.dumps(log_entry))

    return jsonify(upstream_data)

if __name__ == '__main__':
    app.run(debug=True)
