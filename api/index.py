import os
import requests
from flask import Flask, request, jsonify, render_template
from datetime import datetime
from dateutil import parser

app = Flask(__name__, template_folder='../templates')

TARGET_API_BASE = "https://ft-osint-api.duckdns.org/api"
UPSTREAM_DEFAULT_KEY = "vernex-6a9dc4fdd5923c40b0aba27bf1e39e3f"

# Master Database Simulation Matrix
DB = {
    "keys": {
        "SHAYAN-MASTER": {
            "name": "Master Enterprise Dev",
            "key": "SHAYAN-MASTER",
            "expire_date": "2026-12-31T23:59",
            "limit": 1000,
            "used": 0,
            "status": "Active",
            "tools": ["all"]
        }
    },
    "logs": []
}

SUPPORTED_TOOLS = [
    "adv", "paytm", "imei", "calltracer", "upi", "ifsc", 
    "number", "pincode", "ip", "challan", "ff", "bgmi", 
    "snap", "email", "vehicle", "git", "insta", "tg", 
    "tgidinfo", "numleak"
]

def check_key_validity(api_key, tool_name):
    if api_key not in DB["keys"]:
        return False, "Invalid API Key signature."
    
    key_data = DB["keys"][api_key]
    
    # 1. State Status Suspension Checks
    if key_data.get("status", "Active") == "Suspended":
        return False, "This API access footprint has been explicitly suspended."
    
    # 2. Expiration Validation Engine
    try:
        expire_dt = parser.parse(key_data["expire_date"])
        if datetime.now() > expire_dt:
            return False, f"API Key expired automatically on {key_data['expire_date']}."
    except Exception:
        return False, "System runtime token configuration parse structural exception."
    
    # 3. Usage Cap Enforcement
    if int(key_data["used"]) >= int(key_data["limit"]):
        return False, f"Allocated request parameters quota threshold limit reached ({key_data['limit']})."
    
    # 4. Strict Granular Tool Matching Checks
    allowed_tools = key_data.get("tools", [])
    if "all" not in allowed_tools and tool_name not in allowed_tools:
        return False, f"Access denied. Key restricted from using router parameter: '{tool_name}'."
    
    return True, key_data

def sanitize_payload(data):
    banned = ["@ftgamer2", "@bornex", "Ultra", "ft-osint", "duckdns"]
    if isinstance(data, dict):
        return {k: sanitize_payload(v) for k, v in data.items() if not any(b in str(k) for b in banned)}
    elif isinstance(data, list):
        return [sanitize_payload(i) for i in data]
    elif isinstance(data, str):
        for b in banned:
            data = data.replace(b, "SHAYAN_EXPLORER")
        return data
    return data

# --- ADMIN REST MANAGEMENT COMPONENT ROUTING ---

@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/api/admin/keys', methods=['GET', 'POST'])
def handle_keys():
    if request.method == 'POST':
        data = request.json or {}
        key_id = data.get('key')
        if not key_id:
            return jsonify({"status": "error", "message": "Key code input signature is mandatory"}), 400
        
        # Creates or securely merges updates seamlessly (Edit / Re-add)
        DB["keys"][key_id] = {
            "name": data.get('name', 'Client Target Profile'),
            "key": key_id,
            "expire_date": data.get('expire_date', '2026-12-31T23:59'),
            "limit": int(data.get('limit', 100)),
            "used": DB["keys"].get(key_id, {}).get("used", 0), # Preserve data metrics on edit
            "status": data.get('status', DB["keys"].get(key_id, {}).get("status", "Active")),
            "tools": data.get('tools', ['all'])
        }
        return jsonify({"status": "success"})
    return jsonify(list(DB["keys"].values()))

@app.route('/api/admin/keys/status', methods=['POST'])
def change_status():
    data = request.json or {}
    key_id = data.get('key')
    new_status = data.get('status')
    if key_id in DB["keys"]:
        DB["keys"][key_id]["status"] = new_status
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Token not found"}), 404

@app.route('/api/admin/keys/delete/<key_id>', methods=['DELETE'])
def drop_key(key_id):
    if key_id in DB["keys"]:
        del DB["keys"][key_id]
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

@app.route('/api/admin/logs', methods=['GET'])
def fetch_logs():
    return jsonify(DB["logs"])

# --- THE ALL-IN-ONE PROXY GATEWAY ENGINE ---

@app.route('/api/<tool>', methods=['GET'])
def proxy_gateway(tool):
    if tool not in SUPPORTED_TOOLS:
        return jsonify({"status": "error", "developer": "SHAYAN_EXPLORER", "message": "Invalid Route."}), 404

    user_key = request.args.get('key')
    if not user_key:
        return jsonify({"status": "error", "developer": "SHAYAN_EXPLORER", "message": "Missing key parameters."}), 401

    is_valid, result = check_key_validity(user_key, tool)
    if not is_valid:
        return jsonify({"status": "error", "developer": "SHAYAN_EXPLORER", "message": result}), 403

    key_data = result

    # Identify transaction payload details
    search_query = "Dynamic Data Request"
    for param in ['num', 'email', 'vehicle', 'username', 'uid', 'id', 'upi', 'ifsc', 'imei', 'ip', 'pin', 'info']:
        if request.args.get(param):
            search_query = f"{param}: {request.args.get(param)}"
            break

    upstream_params = dict(request.args)
    upstream_params['key'] = UPSTREAM_DEFAULT_KEY

    try:
        response = requests.get(f"{TARGET_API_BASE}/{tool}", params=upstream_params, timeout=12)
        try:
            response_data = sanitize_payload(response.json())
        except ValueError:
            response_data = {"data": sanitize_payload(response.text)}
    except Exception as e:
        response_data = {"status": "error", "message": f"Link failure: {str(e)}"}

    key_data["used"] += 1
    DB["logs"].insert(0, {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "key_name": key_data["name"],
        "key": user_key,
        "tool": tool.upper(),
        "search": search_query,
        "status": "Success" if response.status_code == 200 else "Failed"
    })

    if isinstance(response_data, dict):
        response_data["developer"] = "SHAYAN_EXPLORER"
        response_data["status"] = "SUCCESS"

    return jsonify(response_data), response.status_code

if __name__ == '__main__':
    app.run(debug=True, port=5000)
