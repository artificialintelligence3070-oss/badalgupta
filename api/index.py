import os
import time
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Vercel की परमानेंट फ़ाइल पाथ (यह सर्वर रीस्टार्ट होने पर भी डेटा बचा कर रखता है)
DB_FILE = "/tmp/keys_vault.json"
LOG_FILE = "/tmp/history_logs.json"

def load_vault():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_vault(data):
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass

def load_logs():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_logs(data):
    try:
        with open(LOG_FILE, 'w') as f:
            json.dump(data[:100], f) # मैक्सिमम 100 लॉक्स सेव रखें
    except:
        pass

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
    vault = load_vault()
    if request.method == 'POST':
        data = request.json or {}
        
        # फ्रंटएंड सिंक सपोर्ट
        if "sync_list" in data:
            for item in data.get("sync_list", []):
                k_str = item.get("key")
                if k_str:
                    vault[k_str] = item
            save_vault(vault)
            return jsonify({"success": True, "status": "synced"})

        custom_key = data.get('key')
        if not custom_key: return jsonify({"error": "Key is required"}), 400
        
        vault[custom_key] = {
            "name": data.get('name', 'Premium Client'),
            "key": custom_key,
            "price": float(data.get('price', 0) or 0),
            "daily_limit": int(data.get('daily_limit', 2000)),
            "expire_date": data.get('expire_date', '2026-12-31'),
            "status": data.get('status', 'on'),
            "allow_number": "true" if str(data.get('allow_number')).lower() == "true" else "false",
            "allow_vehicle": "true" if str(data.get('allow_vehicle')).lower() == "true" else "false",
            "allow_aadhar": "true" if str(data.get('allow_aadhar')).lower() == "true" else "false",
            "allow_family": "true" if str(data.get('allow_family')).lower() == "true" else "false",
            "allow_insta": "true" if str(data.get('allow_insta')).lower() == "true" else "false"
        }
        save_vault(vault)
        return jsonify({"success": True})
        
    return jsonify({"keys": list(vault.values())})

@app.route('/api/admin/keys/delete', methods=['POST'])
def delete_key():
    vault = load_vault()
    logs = load_logs()
    data = request.json or {}
    target_key = data.get('key')
    
    # 1. मुख्य डेटाबेस से की (Key) को डिलीट करें
    if target_key in vault:
        del vault[target_key]
        save_vault(vault)
        
    # 2. इतिहास (History) से भी इस की के सारे पुराने रिकॉर्ड्स को साफ़ (Purge) करें
    updated_logs = [log for log in logs if log.get('key_used') != target_key]
    save_logs(updated_logs)
    
    return jsonify({"success": True, "purged": True})

@app.route('/api/admin/toggle', methods=['POST'])
def toggle_key():
    vault = load_vault()
    data = request.json or {}
    key_name = data.get('key')
    if key_name in vault:
        current = vault[key_name].get('status', 'on')
        vault[key_name]['status'] = 'off' if current == 'on' else 'on'
        save_vault(vault)
    return jsonify({"success": True})

@app.route('/api/admin/history', methods=['GET'])
def get_history():
    return jsonify({"history": load_logs()})

def execute_proxy(tool_name, query_param, tracking_label):
    vault = load_vault()
    logs = load_logs()
    
    client_key = request.args.get('key')
    lookup_input = request.args.get(query_param)
    
    if not lookup_input: return jsonify({"error": f"Missing param '{query_param}'"}), 400
    if not client_key or client_key not in vault: 
        return jsonify({"error": "Unauthorized API Key"}), 403
        
    key_meta = vault[client_key]
    if key_meta.get("status", "on") != "on": return jsonify({"error": "Key Suspended"}), 403
    
    # ऑटो-एक्सपायरी चेक
    current_date = time.strftime("%Y-%m-%d")
    if current_date > key_meta.get("expire_date", "2026-12-31"):
        del vault[client_key]
        save_vault(vault)
        return jsonify({"error": "Key Expired Automatically"}), 403
        
    if key_meta.get(f"allow_{tool_name}", "false") != "true": return jsonify({"error": "Access Denied"}), 403
    
    try:
        target_url = f"{TOOLS_CONFIG[tool_name]}&{query_param}={lookup_input}"
        response = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        upstream_data = clean_branding_data(response.json() if response.status_code == 200 else {"raw": response.text})
    except Exception as e:
        return jsonify({"error": "Upstream timeout", "details": str(e)}), 502
        
    log_query = "[Masked]" if "aadhar" in tool_name else lookup_input
    logs.insert(0, {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "key_used": client_key,
        "client_name": key_meta.get("name"),
        "type": tracking_label,
        "query": log_query,
        "status_code": response.status_code
    })
    save_logs(logs)
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
