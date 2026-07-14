import os
import sqlite3
import uuid
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_FILE = "api_gateway.db"
PRIMARY_API_KEY = "explorer16"
BASE_API_URL = "https://ft-osint-api.duckdns.org/api"

# --- BRANDING CONFIGURATION ---
MY_NAME = "SHAYAN_EXPLORER"
MY_URL = "https://shayan-explorer.info"  # Replace with your actual URL if needed

# --- DATABASE SETUP ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        # Admin table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
        ''')
        # API Keys table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT,
                key_value TEXT UNIQUE,
                expiry_date TEXT,
                daily_limit INTEGER,
                current_usage INTEGER DEFAULT 0,
                last_reset_date TEXT,
                allowed_tools TEXT, -- Comma-separated list or 'all'
                is_active INTEGER DEFAULT 1
            )
        ''')
        # Log History table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT,
                tool_used TEXT,
                query_param TEXT,
                timestamp TEXT
            )
        ''')
        
        # Insert default administrator if not present
        try:
            conn.execute(
                "INSERT INTO admins (username, password) VALUES (?, ?)",
                ("vernex", "vernex@16vx")
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass

init_db()

# --- HELPER FUNCTIONS ---
def clean_response_branding(data):
    """
    Recursively scans the response data and swaps old branding text 
    with your custom branding configurations.
    """
    if isinstance(data, str):
        data = data.replace("@ftgamer2", MY_NAME)
        data = data.replace("@bornex Ultra", MY_NAME)
        # Add replacements for specific channel links here if needed
        return data
    elif isinstance(data, dict):
        return {k: clean_response_branding(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_response_branding(item) for item in data]
    return data

def verify_and_update_key(api_key, tool_name):
    """
    Validates the custom key, checks limits, handles daily usage resets, 
    and checks tool restrictions.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()
    
    conn = get_db_connection()
    key_info = conn.execute("SELECT * FROM api_keys WHERE key_value = ?", (api_key,)).fetchone()
    
    if not key_info:
        conn.close()
        return False, "Invalid API Key"
    
    if not key_info['is_active']:
        conn.close()
        return False, "This API key has been deactivated by the admin."
        
    # Check Expiration
    try:
        expiry = datetime.strptime(key_info['expiry_date'], "%Y-%m-%d %H:%M")
        if now > expiry:
            conn.close()
            return False, "API Key has expired."
    except ValueError:
        conn.close()
        return False, "Internal error processing key expiration layout."

    # Check/Reset Daily Usage Limit
    current_usage = key_info['current_usage']
    if key_info['last_reset_date'] != today_str:
        conn.execute("UPDATE api_keys SET current_usage = 0, last_reset_date = ? WHERE id = ?", (today_str, key_info['id']))
        conn.commit()
        current_usage = 0

    if current_usage >= key_info['daily_limit']:
        conn.close()
        return False, "Daily request limit reached for this API key."

    # Check Tool Accessibility
    allowed = key_info['allowed_tools']
    if allowed != 'all':
        allowed_list = [t.strip() for t in allowed.split(',')]
        if tool_name not in allowed_list:
            conn.close()
            return False, f"This key does not have access to the [{tool_name}] tool."

    # Update usage counts
    conn.execute("UPDATE api_keys SET current_usage = current_usage + 1 WHERE id = ?", (key_info['id'],))
    conn.commit()
    conn.close()
    
    return True, key_info['key_name']

def log_request(key_name, tool, query):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO request_logs (key_name, tool_used, query_param, timestamp) VALUES (?, ?, ?, ?)",
            (key_name, tool, query, timestamp)
        )
        conn.commit()

# --- WEB DASHBOARD INTERFACE (HTML/CSS Embedded Template) ---
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SHAYAN_EXPLORER | Admin Central Suite</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: #0f172a; color: #e2e8f0; font-family: 'Inter', sans-serif; }
        .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.05); }
    </style>
</head>
<body class="p-4 md:p-8">
    <div class="max-w-7xl mx-auto">
        <div class="flex justify-between items-center mb-8 glass rounded-2xl p-6 shadow-2xl">
            <div>
                <h1 class="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500 tracking-wider">SHAYAN_EXPLORER</h1>
                <p class="text-xs text-slate-400 mt-1 uppercase tracking-widest">Advanced Central API Controller Engine</p>
            </div>
            <a href="{{ url_for('logout') }}" class="bg-red-500/20 hover:bg-red-500/40 text-red-400 font-bold py-2 px-4 rounded-xl border border-red-500/30 transition duration-300">
                <i class="fa-solid fa-power-off mr-2"></i>Logout
            </a>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div class="glass rounded-2xl p-6 shadow-xl h-fit">
                <h2 class="text-xl font-bold mb-4 text-cyan-400 border-b border-slate-700 pb-2"><i class="fa-solid fa-key mr-2"></i>Provision New Access Key</h2>
                <form action="{{ url_for('create_key') }}" method="POST" class="space-y-4">
                    <div>
                        <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1">Key Description/Name</label>
                        <input type="text" name="key_name" placeholder="e.g., Premium User Client X" required class="w-full bg-slate-900/60 border border-slate-700 rounded-xl p-3 text-sm focus:outline-none focus:border-cyan-500">
                    </div>
                    <div>
                        <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1">Daily Total Request Limit</label>
                        <input type="number" name="daily_limit" placeholder="e.g., 500" required class="w-full bg-slate-900/60 border border-slate-700 rounded-xl p-3 text-sm focus:outline-none focus:border-cyan-500">
                    </div>
                    <div>
                        <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1">Expiration Cut-off (Date & Time)</label>
                        <input type="datetime-local" name="expiry_date" required class="w-full bg-slate-900/60 border border-slate-700 rounded-xl p-3 text-sm focus:outline-none focus:border-cyan-500">
                    </div>
                    <div>
                        <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1">Scope of Authorized Tools</label>
                        <select name="allowed_tools" class="w-full bg-slate-900/60 border border-slate-700 rounded-xl p-3 text-sm focus:outline-none focus:border-cyan-500">
                            <option value="all">Grant Access to All Tools</option>
                            <option value="adv,paytm,imei,calltracer,upi,ifsc">Finance & Identifiers Only</option>
                            <option value="snap,git,insta,tg,tgidinfo">Social Intelligence Only</option>
                            <option value="vehicle,challan,pincode">Logistics & Infrastructure Only</option>
                        </select>
                    </div>
                    <button type="submit" class="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white font-bold py-3 px-4 rounded-xl shadow-lg transition duration-300">
                        Generate Secure Endpoint Key
                    </button>
                </form>
            </div>

            <div class="lg:grid-cols-1 lg:col-span-2 space-y-8">
                <div class="glass rounded-2xl p-6 shadow-xl">
                    <h2 class="text-xl font-bold mb-4 text-blue-400 border-b border-slate-700 pb-2"><i class="fa-solid fa-folder-tree mr-2"></i>Active Provisioned API Keys</h2>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="text-slate-400 text-xs uppercase tracking-wider border-b border-slate-700">
                                    <th class="pb-3">Label</th>
                                    <th class="pb-3">Secret Key Hash String</th>
                                    <th class="pb-3">Reset usage / Cap</th>
                                    <th class="pb-3">Expires At</th>
                                    <th class="pb-3 text-center">Status</th>
                                    <th class="pb-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-800 text-sm">
                                {% for key in keys %}
                                <tr>
                                    <td class="py-3 font-semibold text-slate-200">{{ key.key_name }}</td>
                                    <td class="py-3 font-mono text-cyan-300 text-xs">{{ key.key_value }}</td>
                                    <td class="py-3">{{ key.current_usage }} / <span class="text-slate-400">{{ key.daily_limit }}</span></td>
                                    <td class="py-3 text-xs text-amber-400">{{ key.expiry_date }}</td>
                                    <td class="py-3 text-center">
                                        {% if key.is_active %}
                                        <span class="px-2 py-1 text-xs font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">LIVE</span>
                                        {% else: %}
                                        <span class="px-2 py-1 text-xs font-bold rounded-full bg-slate-500/20 text-slate-400 border border-slate-500/30">MUTED</span>
                                        {% endif %}
                                    </td>
                                    <td class="py-3 text-right space-x-2">
                                        <a href="{{ url_for('toggle_key', key_id=key.id) }}" class="text-xs font-bold py-1 px-2.5 rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20 transition">Switch</a>
                                        <a href="{{ url_for('delete_key', key_id=key.id) }}" onclick="return confirm('Permanently wipe out this key?')" class="text-xs font-bold py-1 px-2.5 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition">Drop</a>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="glass rounded-2xl p-6 shadow-xl">
                    <h2 class="text-xl font-bold mb-4 text-purple-400 border-b border-slate-700 pb-2"><i class="fa-solid fa-clock-history mr-2"></i>Global Metric Search Logs</h2>
                    <div class="overflow-y-auto max-h-64">
                        <table class="w-full text-left text-sm">
                            <thead>
                                <tr class="text-slate-400 text-xs border-b border-slate-700">
                                    <th class="pb-2">Key Owner</th>
                                    <th class="pb-2">Target Tool</th>
                                    <th class="pb-2">Evaluated Parameter Query</th>
                                    <th class="pb-2 text-right">Timestamp</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-800 text-xs">
                                {% for log in logs %}
                                <tr class="hover:bg-slate-800/30 transition">
                                    <td class="py-2 text-slate-300 font-medium">{{ log.key_name }}</td>
                                    <td class="py-2"><span class="bg-purple-500/10 text-purple-400 border border-purple-500/20 px-1.5 py-0.5 rounded font-mono">{{ log.tool_used }}</span></td>
                                    <td class="py-2 font-mono text-slate-400">{{ log.query_param }}</td>
                                    <td class="py-2 text-right text-slate-500">{{ log.timestamp }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Gateway Authentication</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body { background: #0f172a; color: #e2e8f0; }</style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="w-full max-w-md bg-slate-800/80 backdrop-blur-md p-8 rounded-2xl border border-slate-700 shadow-2xl">
        <h2 class="text-2xl font-black text-center mb-2 tracking-wide text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">GATEWAY INTERACTION PANEL</h2>
        <p class="text-center text-xs text-slate-400 uppercase tracking-widest mb-6">Identity Check Required</p>
        
        {% if error %}
        <div class="bg-red-500/10 border border-red-500/30 text-red-400 text-sm p-3 rounded-xl mb-4 text-center font-semibold">
            {{ error }}
        </div>
        {% endif %}

        <form action="{{ url_for('login') }}" method="POST" class="space-y-4">
            <div>
                <input type="text" name="username" placeholder="Username Key" required class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-cyan-500">
            </div>
            <div>
                <input type="password" name="password" placeholder="Security Pin Access" required class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-cyan-500">
            </div>
            <button type="submit" class="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold py-3 px-4 rounded-xl shadow-lg hover:from-cyan-600 hover:to-blue-700 transition duration-300">
                Establish Authorized Session
            </button>
        </form>
    </div>
</body>
</html>
"""

# --- ROUTING LOGIC ---

@app.route('/')
def home():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM admins WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        
        if admin:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error="System match not found. Access Rejected.")
            
    return render_template_string(LOGIN_TEMPLATE, error=None)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    keys = conn.execute("SELECT * FROM api_keys ORDER BY id DESC").fetchall()
    logs = conn.execute("SELECT * FROM request_logs ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    
    return render_template_string(DASHBOARD_TEMPLATE, keys=keys, logs=logs)

@app.route('/key/create', methods=['POST'])
def create_key():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    name = request.form.get('key_name')
    daily_limit = request.form.get('daily_limit')
    expiry_date = request.form.get('expiry_date')  # Formats as YYYY-MM-DDTHH:MM
    allowed_tools = request.form.get('allowed_tools')
    
    # Clean datetime format to standard display: YYYY-MM-DD HH:MM
    if expiry_date:
        expiry_date = expiry_date.replace('T', ' ')
        
    generated_key = f"shayan_{uuid.uuid4().hex[:12]}"
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO api_keys (key_name, key_value, expiry_date, daily_limit, last_reset_date, allowed_tools) VALUES (?, ?, ?, ?, ?, ?)",
            (name, generated_key, expiry_date, daily_limit, today_str, allowed_tools)
        )
        conn.commit()
        
    return redirect(url_for('dashboard'))

@app.route('/key/toggle/<int:key_id>')
def toggle_key(key_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    with get_db_connection() as conn:
        conn.execute("UPDATE api_keys SET is_active = 1 - is_active WHERE id = ?", (key_id,))
        conn.commit()
    return redirect(url_for('dashboard'))

@app.route('/key/delete/<int:key_id>')
def delete_key(key_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    with get_db_connection() as conn:
        conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        conn.commit()
    return redirect(url_for('dashboard'))

# --- CORE API ENGINE PROXY (METERED, LOGGED & RE-BRANDED) ---

@app.route('/api/<tool_name>', methods=['GET'])
def proxy_gateway(tool_name):
    # Collect inbound verification parameters
    custom_key = request.args.get('key')
    
    if not custom_key:
        return jsonify({"status": "failed", "error": "Missing validation element [key]"}), 400
        
    # Check what identification parameter parameter was supplied in the request string
    query_param = "None"
    forward_params = {'key': PRIMARY_API_KEY}
    
    for param in ['num', 'imei', 'upi', 'ifsc', 'pin', 'ip', 'vehicle', 'uid', 'username', 'email', 'info', 'id']:
        if request.args.get(param):
            query_param = request.args.get(param)
            forward_params[param] = query_param
            break

    # 1. Authorization & Limit Inspection Checks
    is_valid, message_or_name = verify_and_update_key(custom_key, tool_name)
    if not is_valid:
        return jsonify({"status": "failed", "error": message_or_name}), 403

    # 2. Complete Search Log Registration
    log_request(message_or_name, tool_name, query_param)

    # 3. Request Proxy Delegation to core node
    target_url = f"{BASE_API_URL}/{tool_name}"
    try:
        response = requests.get(target_url, params=forward_params, timeout=12)
        
        # Parse output data cleanly
        try:
            raw_json = response.json()
            # 4. Filter and Inject Custom Developer Identity Signatures
            sanitized_data = clean_response_branding(raw_json)
            return jsonify(sanitized_data), response.status_code
        except ValueError:
            # Fallback handling for basic text/raw stream updates
            sanitized_text = clean_response_branding(response.text)
            return sanitized_text, response.status_code

    except requests.exceptions.RequestException:
        return jsonify({"status": "error", "message": "The root query engine failed to answer safely."}), 502

if __name__ == '__main__':
    # Initial execution parameters
    app.run(host='0.0.0.0', port=5000, debug=True)
