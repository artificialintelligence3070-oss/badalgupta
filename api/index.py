import os
import time
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from redis import Redis

app = Flask(__name__)
# मोबाइल ऐप्स और फ्रंटएंड कनेक्टिविटी के लिए CORS को ओपन रखा गया है
CORS(app)

# Persistent Vercel KV Redis Cloud Initialization
KV_URL = os.environ.get("KV_URL", "")
if KV_URL.startswith("redis://") or KV_URL.startswith("rediss://"):
    db = Redis.from_url(KV_URL, decode_responses=True)
else:
    class MockRedis:
        def __init__(self): self.data = {}
        def get(self, k): return self.data.get(k)
        def set(self, k, v): self.data[k] = str(v); return True
        def hgetall(self, k): return self.data.get(k, {})
        def hset(self, k, mapping=None):
            if k not in self.data: self.data[k] = {}
            if mapping: self.data[k].update(mapping)
            return len(mapping)
        def hdel(self, k, field):
            if k in self.data and field in self.data[k]:
                del self.data[k][field]
                return 1
            return 0
        def del_key(self, k):
            if k in self.data: del self.data[k]; return 1
            return 0
        def keys(self, p): return [k for k in self.data.keys() if k.startswith(p.replace('*',''))]
        def lpush(self, k, v):
            if k not in self.data: self.data[k] = []
            self.data[k].insert(0, v)
        def lrange(self, k, s, e): return self.data.get(k, [])[:50]
    db = MockRedis()

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
    """पुराने सभी नामों को हटाकर रिस्पॉन्स में केवल आपका नाम और चैनल सेट करता है"""
    data_str = json.dumps(data)
    
    # पुराने नामों और लिंक्स को पूरी तरह डिलीट करके शयान एक्सप्लोरर नेटवर्क पर मैप किया गया
    data_str = data_str.replace("@ftgamer2", "shayan_explorer").replace("@FTgamer2", "shayan_explorer")
    data_str = data_str.replace("FTgamer2", "shayan_explorer").replace("ftgamer2", "shayan_explorer")
    data_str = data_str.replace("https://t.me/lynx_api", "https://t.me/shayan_explorer_channel")
    data_str = data_str.replace("https://t.me/FTgamer2", "https://t.me/shayan_explorer_channel")
    
    cleaned = json.loads(data_str)
    if isinstance(cleaned, dict):
        cleaned["by"] = "shayan_explorer"
        cleaned["channel"] = "https://t.me/shayan_explorer_channel"
    return cleaned

def validate_custom_key(client_key, required_tool):
    if not client_key: return {"error": "Missing parameter 'key'"}, 400
    key_meta = db.hgetall(f"apikey:{client_key}")
    if not key_meta: return {"error": "Unauthorized: Invalid API Key"}, 403
    if key_meta.get("status", "on") != "on": return {"error": "Forbidden: Key suspended"}, 403
    if key_meta.get(f"allow_{required_tool}", "false") != "true":
        return {"error": f"Access Denied: Lacks {required_tool} permissions."}, 403
        
    current_date = time.strftime("%Y-%m-%d")
    if current_date > key_meta.get("expire_date", "2030-12-31"):
        return {"error": "Expired: Token execution timeline passed"}, 403
        
    usage_key = f"usage:{client_key}:{current_date}"
    current_usage = int(db.get(usage_key) or 0)
    if current_usage >= int(key_meta.get("daily_limit", 100)):
        return {"error": "Rate Limit Exceeded: Capacity reached"}, 429
        
    return {"success": True, "meta": key_meta, "usage_key": usage_key, "current_usage": current_usage}, 200

# --- CONTROL MANAGERS (ADMIN INTEGRATED ENDPOINTS) ---

@app.route('/api/admin/metrics', methods=['GET'])
def get_metrics():
    current_date = time.strftime("%Y-%m-%d")
    keys_in_db = db.keys("apikey:*")
    
    total_revenue = 0
    total_calls_today = 0
    
    for k in keys_in_db:
        meta = db.hgetall(k)
        if meta:
            total_revenue += float(meta.get("price", 0) or 0)
            key_str = meta.get("key")
            usage_val = db.get(f"usage:{key_str}:{current_date}")
            if usage_val:
                total_calls_today += int(usage_val)
                
    return jsonify({
        "total_keys": len(keys_in_db),
        "today_income": total_revenue,
        "today_volume": total_calls_today
    })

@app.route('/api/admin/keys', methods=['GET', 'POST'])
def manage_keys():
    if request.method == 'POST':
        data = request.json or {}
        custom_key = data.get('key', f"shayan-{int(time.time())}")
        
        db.hset(f"apikey:{custom_key}", mapping={
            "name": data.get('name', 'Client Reference'),
            "key": custom_key,
            "price": float(data.get('price', 0) or 0),
            "daily_limit": int(data.get('daily_limit', 1000)),
            "expire_date": data.get('expire_date', '2027-12-31'),
            "status": "on",
            "allow_number": "true" if data.get('allow_number') else "false",
            "allow_vehicle": "true" if data.get('allow_vehicle') else "false",
            "allow_aadhar": "true" if data.get('allow_aadhar') else "false",
            "allow_family": "true" if data.get('allow_family') else "false",
            "allow_insta": "true" if data.get('allow_insta') else "false"
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
    if hasattr(db, 'del_key'):
        db.del_key(f"apikey:{target_key}")
    else:
        db.delete(f"apikey:{target_key}")
    return jsonify({"success": True, "message": "Key dropped from database clusters"})

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

# --- CORE INTEGRATED ENDPOINT ROUTERS (DYNAMIC PROXY FIXED) ---

def execute_proxy(tool_name, query_param, tracking_label):
    client_key = request.args.get('key')
    lookup_input = request.args.get(query_param)
    if not lookup_input: return jsonify({"error": f"Missing parameter '{query_param}'"}), 400
    
    res, code = validate_custom_key(client_key, tool_name)
    if code != 200: return jsonify(res), code
    
    try:
        # अपस्ट्रीम यूआरएल के मापदंडों को सही ढंग से सिंक किया गया
        target_url = f"{TOOLS_CONFIG[tool_name]}&{query_param}={lookup_input}"
        response = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        upstream_data = clean_branding_data(response.json() if response.status_code == 200 else {"raw": response.text})
    except Exception as e:
        return jsonify({"error": "Upstream infrastructure cluster timeout", "details": str(e)}), 502
        
    db.set(res["usage_key"], res["current_usage"] + 1)
    
    # सुरक्षा के लिए संवेदनशील इनपुट को केवल लॉग फ़ाइल में मास्क (Omit) किया जाता है
    log_query = "[Aadhaar Redacted]" if "aadhar" in tool_name or "family" in tool_name else lookup_input
    
    db.lpush("api:history", json.dumps({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "key_used": client_key,
        "client_name": res["meta"].get("name"),
        "type": tracking_label,
        "query": log_query,
        "status_code": response.status_code
    }))
    return jsonify(upstream_data)

@app.route('/api/number', methods=['GET'])
def lookup_num(): 
    return execute_proxy("number", "num", "NUMBER LOOKUP")

@app.route('/api/vehicle', methods=['GET'])
def lookup_veh(): 
    return execute_proxy("vehicle", "vehicle", "VEHICLE LOOKUP")

@app.route('/api/aadhar', methods=['GET'])
def lookup_adr(): 
    return execute_proxy("aadhar", "num", "AADHAR LOOKUP")

@app.route('/api/adharfamily', methods=['GET'])
def lookup_fam(): 
    return execute_proxy("family", "num", "FAMILY LOOKUP")

@app.route('/api/insta', methods=['GET'])
def lookup_ins(): 
    return execute_proxy("insta", "username", "INSTAGRAM TRACE")

# Vercel Serverless Function Deployment के लिए आवश्यक Handler Interface
def handler(request):
    return app(request)

if __name__ == '__main__':
    app.run(debug=True)
