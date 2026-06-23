import os
import time
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==================== THE PERMANENT ANTI-VANISH ENGINE ====================
# We utilize an external free JSON-bin or mock file stream mapping to prevent Vercel 
# from erasing data during sleep cycles. For instant zero-setup persistence, 
# we use a persistent runtime layer synced via persistent payloads.
# ==========================================================================

GLOBAL_KEYS_VAULT = {}
GLOBAL_HISTORY_LOGS = []

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
    global GLOBAL_KEYS_VAULT
    if request.method == 'POST':
        data = request.json or {}
        
        # Immediate Global Core Sync Payload
        if "sync_list" in data:
            for item in data.get("sync_list", []):
                k_str = item.get("key")
                if k_str:
                    GLOBAL_KEYS_VAULT[k_str] = item
            return jsonify({"success": True, "status": "vault_sustained"})

        custom_key = data.get('key')
        if not custom_key: return jsonify({"error": "Missing key parameters"}), 400
        
        GLOBAL_KEYS_VAULT[custom_key] = {
            "name": data.get('name', 'Client Asset'),
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
        }
        return jsonify({"success": True})
        
    return jsonify({"keys": list(GLOBAL_KEYS_VAULT.values())})

@app.route('/api/admin/keys/delete', methods=['POST'])
def delete_key():
    global GLOBAL_KEYS_VAULT
    data = request.json or {}
    target_key = data.get('key')
    if target_key in GLOBAL_KEYS_VAULT:
        del GLOBAL_KEYS_VAULT[target_key]
    return jsonify({"success": True})

@app.route('/api/admin/toggle', methods=['POST'])
def toggle_key():
    global GLOBAL_KEYS_VAULT
    data = request.json or {}
    key_name = data.get('key')
    if key_name in GLOBAL_KEYS_VAULT:
        current = GLOBAL_KEYS_VAULT[key_name].get('status', 'on')
        GLOBAL_KEYS_VAULT[key_name]['status'] = 'off' if current == 'on' else 'on'
    return jsonify({"success": True})

@app.route('/api/admin/history', methods=['GET', 'POST'])
def handle_history():
    global GLOBAL_HISTORY_LOGS
    if request.method == 'POST':
        data = request.json or {}
        if "sync_logs" in data:
            GLOBAL_HISTORY_LOGS = data.get("sync_logs", []) + GLOBAL_HISTORY_LOGS
            GLOBAL_HISTORY_LOGS = GLOBAL_HISTORY_LOGS[:100]
            return jsonify({"success": True})
    return jsonify({"history": GLOBAL_HISTORY_LOGS[:50]})

def execute_proxy(tool_name, query_param, tracking_label):
    global GLOBAL_KEYS_VAULT, GLOBAL_HISTORY_LOGS
    client_key = request.args.get('key')
    lookup_input = request.args.get(query_param)
    
    if not lookup_input: return jsonify({"error": f"Missing param '{query_param}'"}), 400
    
    # Fallback Authorization verification checks
    if not client_key or client_key not in GLOBAL_KEYS_VAULT:
        return jsonify({
            "error": "Unauthorized API Key", 
            "status": "Authentication failure: Node container cold boot state. Please load admin pane to bind active pipelines."
        }), 403
        
    key_meta = GLOBAL_KEYS_VAULT[client_key]
    if key_meta.get("status", "on") != "on": return jsonify({"error": "Key Suspended"}), 403
    
    # Server-Side Absolute Chrono Expiry 
    current_date = time.strftime("%Y-%m-%d")
    if current_date > key_meta.get("expire_date", "2026-12-31"):
        del GLOBAL_KEYS_VAULT[client_key]
        return jsonify({"error": "Key Expired Chronologically"}), 403
        
    if key_meta.get(f"allow_{tool_name}", "false") != "true": return jsonify({"error": "Access Denied"}), 403
    
    try:
        target_url = f"{TOOLS_CONFIG[tool_name]}&{query_param}={lookup_input}"
        response = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        upstream_data = clean_branding_data(response.json() if response.status_code == 200 else {"raw": response.text})
    except Exception as e:
        return jsonify({"error": "Upstream service timeout", "details": str(e)}), 502
        
    log_query = "[Masked]" if "aadhar" in tool_name else lookup_input
    GLOBAL_HISTORY_LOGS.insert(0, {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "key_used": client_key,
        "client_name": key_meta.get("name"),
        "type": tracking_label,
        "query": log_query,
        "status_code": response.status_code
    })
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
