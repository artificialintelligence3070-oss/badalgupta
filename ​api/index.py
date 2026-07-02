import datetime
import httpx
from typing import Dict, List, Optional
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Initialize FastAPI instance
app = FastAPI(title="SHAYAN_EXPLORER API Gateway")

# Configuration Definitions
ADMIN_USER = "vernex"
ADMIN_PASS = "vernex@16vx"
BASE_TARGET_URL = "https://ft-osint-api.duckdns.org/api"
DEFAULT_UPSTREAM_KEY = "vx-osint"

# In-Memory Database State
api_keys_db: Dict[str, dict] = {}
search_logs: List[dict] = []

# Expanded Tools Blueprint Catalog
# Contains integrated mapping targets for telemetry routing
TOOLS_LIST = [
    {"id": "adv", "name": "Advanced Lookup", "param": "num"},
    {"id": "paytm", "name": "Paytm Lookup", "param": "num"},
    {"id": "imei", "name": "IMEI Lookup", "param": "imei"},
    {"id": "calltracer", "name": "Call Tracer", "param": "num"},
    {"id": "upi", "name": "UPI Verification", "param": "upi"},
    {"id": "ifsc", "name": "IFSC Details", "param": "ifsc"},
    {"id": "number", "name": "Standard Number Lookup", "param": "num"},
    {"id": "pincode", "name": "Pincode Details", "param": "pin"},
    {"id": "ip", "name": "IP Geolocation", "param": "ip"},
    {"id": "challan", "name": "Vehicle Challan", "param": "vehicle"},
    {"id": "ff", "name": "FreeFire UID Info", "param": "uid"},
    {"id": "bgmi", "name": "BGMI UID Info", "param": "uid"},
    {"id": "snap", "name": "Snapchat Info", "param": "username"},
    {"id": "email", "name": "Email to Info", "param": "email"},
    {"id": "vehicle", "name": "Vehicle Lookup", "param": "vehicle"},
    {"id": "git", "name": "GitHub Profile Lookup", "param": "username"},
    {"id": "insta", "name": "Instagram Info", "param": "username"},
    {"id": "tg", "name": "Telegram Username to Num", "param": "info"},
    {"id": "tgidinfo", "name": "Telegram ID to Num", "param": "id"},
    {"id": "numleak", "name": "Number Leak Database", "param": "num"},
    {"id": "pk", "name": "PK Database Lookup", "param": "num"},
    {"id": "name", "name": "Identity Name Search", "param": "name"},
    {"id": "aadhar", "name": "UID Verification System", "param": "num"},
    {"id": "numtoupi", "name": "Number to UPI Mapping", "param": "num"},
    {"id": "pan", "name": "PAN Verification Check", "param": "pan"},
    {"id": "veh2num", "name": "Vehicle to Mobile Mapping", "param": "vehicle"},
    {"id": "adharfamily", "name": "Family Struct Verification", "param": "num"},
    {"id": "bomber", "name": "Verification SMS Engine", "param": "number"},
]

class LoginRequest(BaseModel):
    username: str
    password: str

class KeyGenRequest(BaseModel):
    key_name: str
    custom_key: str
    daily_limit: int
    expiry_date: str
    allowed_tools: List[str]

# --- REVERSE PROXY GATEWAY ROUTE (WITH AUTOMATIC BRANDING OVERWRITE) ---
@app.get("/gateway/{tool_id}")
async def gateway_router(tool_id: str, request: Request):
    query_params = dict(request.query_params)
    user_key = query_params.get("key")
    
    if not user_key or user_key not in api_keys_db:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    key_data = api_keys_db[user_key]
    
    if key_data["status"] == "suspended":
        raise HTTPException(status_code=403, detail="API Key is suspended")
        
    expiry = datetime.datetime.strptime(key_data["expiry"], "%Y-%m-%d").date()
    if datetime.date.today() > expiry:
        raise HTTPException(status_code=403, detail="API Key has expired")
        
    if key_data["uses"] >= key_data["limit"]:
        raise HTTPException(status_code=429, detail="API Key request limit reached")
        
    if "all" not in key_data["tools"] and tool_id not in key_data["tools"]:
        raise HTTPException(status_code=403, detail="This key is not authorized to use this specific tool")

    tool_config = next((t for t in TOOLS_LIST if t["id"] == tool_id), None)
    search_query = "Unknown Query"
    if tool_config:
        search_query = query_params.get(tool_config["param"], "N/A")

    # Tracking log allocation entry
    search_logs.append({
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "key_name": key_data["name"],
        "key": user_key,
        "tool": tool_id,
        "query": search_query
    })
    
    key_data["uses"] += 1
    
    if not tool_config:
        raise HTTPException(status_code=404, detail="Tool Endpoint Not Found")
        
    forward_params = query_params.copy()
    forward_params["key"] = DEFAULT_UPSTREAM_KEY 
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_TARGET_URL}/{tool_id}", params=forward_params, timeout=12.0)
            
            # Intercept and scrub response data structures directly before rendering
            if response.status_code == 200:
                try:
                    res_data = response.json()
                    if isinstance(res_data, dict):
                        # Clean and assign personal identity parameters
                        res_data["by"] = "@vernexzzz"
                        res_data["channel"] = "https://t.me/shayan_explorer_channel"
                        
                        # Extra cleaning safety pass if alternate metadata fields exist
                        if "creator" in res_data:
                            res_data["creator"] = "@vernexzzz"
                        if "owner" in res_data:
                            res_data["owner"] = "@vernexzzz"
                            
                    return JSONResponse(status_code=response.status_code, content=res_data)
                except Exception:
                    # Pass default response if non-serializable response payload occurs
                    pass
                    
            return JSONResponse(status_code=response.status_code, content=response.json())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": "Upstream timeout or host down", "details": str(e)})

# --- ADMIN ENDPOINTS ---
@app.post("/api/admin/login")
def admin_login(data: LoginRequest):
    if data.username == ADMIN_USER and data.password == ADMIN_PASS:
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/admin/data")
def get_admin_data():
    return {
        "keys": list(api_keys_db.values()),
        "logs": search_logs[-100:],
        "tools": TOOLS_LIST
    }

@app.post("/api/admin/keys")
def create_key(data: KeyGenRequest):
    if data.custom_key in api_keys_db:
        raise HTTPException(status_code=400, detail="Key already exists")
    
    api_keys_db[data.custom_key] = {
        "name": data.key_name,
        "key": data.custom_key,
        "limit": data.daily_limit,
        "uses": 0,
        "expiry": data.expiry_date,
        "tools": data.allowed_tools,
        "status": "active"
    }
    return {"status": "created"}

@app.post("/api/admin/keys/{key_id}/action")
def modify_key(key_id: str, action: dict):
    if key_id not in api_keys_db:
        raise HTTPException(status_code=404, detail="Key not found")
    
    act_type = action.get("type")
    if act_type == "delete":
        del api_keys_db[key_id]
    elif act_type == "suspend":
        api_keys_db[key_id]["status"] = "suspended"
    elif act_type == "activate":
        api_keys_db[key_id]["status"] = "active"
    elif act_type == "restart_limit":
        api_keys_db[key_id]["uses"] = 0
    elif act_type == "edit":
        api_keys_db[key_id]["limit"] = action.get("limit")
        api_keys_db[key_id]["expiry"] = action.get("expiry")
    return {"status": "updated"}

# --- DASHBOARD RENDERING INTERFACE ---
@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SHAYAN_EXPLORER // CONTROL SUITE</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght=300;400;600;800&family=Space+Grotesk:wght=400;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #040406; }
            .mono { font-family: 'Space Grotesk', sans-serif; }
            .glass-panel { background: rgba(11, 12, 22, 0.6); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.03); }
        </style>
    </head>
    <body class="text-slate-200 min-h-screen">

        <!-- LOGIN SCREEN -->
        <div id="loginView" class="fixed inset-0 bg-[#040406] z-50 flex items-center justify-center p-4">
            <div class="w-full max-w-md bg-[#0a0b12] border border-slate-900 rounded-2xl p-8 shadow-2xl">
                <div class="mb-8 text-center">
                    <span class="text-xs uppercase tracking-widest text-indigo-400 font-bold mono">Developed by @vernexzzz</span>
                    <h1 class="text-3xl font-extrabold text-white mt-1">SHAYAN_EXPLORER</h1>
                </div>
                <div class="space-y-4">
                    <div>
                        <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1 font-semibold">Admin Username</label>
                        <input id="admUser" type="text" class="w-full bg-[#111222] border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition-all" placeholder="Username">
                    </div>
                    <div>
                        <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1 font-semibold">Passphrase</label>
                        <input id="admPass" type="password" class="w-full bg-[#111222] border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition-all" placeholder="••••••••">
                    </div>
                    <button onclick="attemptLogin()" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-4 rounded-xl transition-all shadow-lg mt-2">
                        Enter Workspace Terminal
                    </button>
                    <p id="loginErr" class="text-xs text-rose-400 mt-2 hidden text-center mono">Invalid Administrative Credentials.</p>
                </div>
            </div>
        </div>

        <!-- APPLICATION CONTAINER -->
        <div id="appView" class="hidden min-h-screen flex flex-col">
            <header class="border-b border-slate-900 bg-[#07080f]/90 backdrop-blur-md sticky top-0 z-40 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
                <div class="flex items-center gap-3">
                    <div class="h-3 w-3 rounded-full bg-indigo-500 animate-pulse"></div>
                    <span class="font-bold tracking-tight text-lg text-white">SHAYAN_EXPLORER <span class="text-indigo-400 text-xs px-2 py-0.5 rounded border border-indigo-500/20 bg-indigo-500/5 ml-1">BY @VERNEXZZZ</span></span>
                </div>
                <div class="flex items-center gap-3">
                    <a href="https://t.me/shayan_explorer_channel" target="_blank" class="text-xs font-bold text-indigo-400 hover:underline bg-indigo-500/5 border border-indigo-500/20 px-3 py-2 rounded-xl transition-all">
                        📢 Official Channel Link
                    </a>
                    <button onclick="toggleEndpoints()" class="text-xs font-semibold px-4 py-2 bg-[#111322] border border-slate-800 hover:border-slate-700 rounded-xl transition-all">
                        📋 Live Proxy Architecture URIs
                    </button>
                </div>
            </header>

            <div id="endpointsDrawer" class="hidden bg-[#0a0b12] border-b border-slate-900 p-6">
                <div class="max-w-7xl mx-auto">
                    <h3 class="text-sm font-bold uppercase tracking-wider text-indigo-400 mb-3 mono">Production Target Proxy URLs (Click to Copy instantly)</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" id="rawUrlsList"></div>
                </div>
            </div>

            <main class="flex-1 p-6 max-w-7xl w-full mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Management Engine Panel -->
                <div class="lg:col-span-1 space-y-6">
                    <div class="bg-[#080911] border border-slate-900 rounded-2xl p-6">
                        <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <span>🔑</span> Generate Dynamic Token
                        </h2>
                        <div class="space-y-4">
                            <div>
                                <label class="block text-xs uppercase text-slate-400 mb-1 font-semibold">User Label / Client Name</label>
                                <input id="keyName" type="text" placeholder="e.g., Client User Token" class="w-full bg-[#121324] border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-xs uppercase text-slate-400 mb-1 font-semibold">Custom Passkey Core</label>
                                <input id="keyString" type="text" placeholder="e.g., shayan-key-xxxx" class="w-full bg-[#121324] border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                            </div>
                            <div class="grid grid-cols-2 gap-3">
                                <div>
                                    <label class="block text-xs uppercase text-slate-400 mb-1 font-semibold">Limit Request</label>
                                    <input id="keyLimit" type="number" value="500" class="w-full bg-[#121324] border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                                </div>
                                <div>
                                    <label class="block text-xs uppercase text-slate-400 mb-1 font-semibold">Expiration Date</label>
                                    <input id="keyExpiry" type="date" class="w-full bg-[#121324] border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                                </div>
                            </div>
                            
                            <div>
                                <label class="block text-xs uppercase text-slate-400 mb-2 font-semibold">Module Endpoint Scope Rules</label>
                                <div class="flex gap-2 mb-3">
                                    <button id="toolScopeAll" onclick="setScopeMode('all')" class="flex-1 py-1.5 rounded-lg text-xs font-bold border border-indigo-500 bg-indigo-500/10 text-indigo-400">All Modules Enabled</button>
                                    <button id="toolScopeSpec" onclick="setScopeMode('spec')" class="flex-1 py-1.5 rounded-lg text-xs font-bold border border-slate-800 bg-[#121324] text-slate-400">Isolate Specific Tools</button>
                                </div>
                                <div id="specificToolsGrid" class="hidden grid grid-cols-2 gap-2 max-h-40 overflow-y-auto p-2 bg-[#0a0b12] rounded-xl border border-slate-900">
                                    <!-- Dynamic checkboxes drop here -->
                                </div>
                            </div>

                            <button onclick="generateKey()" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 px-4 rounded-xl text-sm transition-all shadow-lg mt-2">
                                Provision Key Ruleset
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Live Stream Panel -->
                <div class="lg:col-span-2 space-y-6">
                    <div class="bg-[#080911] border border-slate-900 rounded-2xl p-6">
                        <h2 class="text-lg font-bold text-white mb-4">Live Cryptographic Allocation Mapping</h2>
                        <div class="space-y-3 max-h-[380px] overflow-y-auto pr-1" id="keysContainer">
                            <!-- Populated allocations inside loop -->
                        </div>
                    </div>

                    <div class="bg-[#080911] border border-slate-900 rounded-2xl p-6">
                        <h2 class="text-lg font-bold text-white mb-4 flex items-center justify-between">
                            <span>📡 Live Activity Lookup Telemetry</span>
                        </h2>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-xs">
                                <thead>
                                    <tr class="border-b border-slate-900 text-slate-400 font-mono">
                                        <th class="py-2">Timestamp</th>
                                        <th class="py-2">Key Owner</th>
                                        <th class="py-2">Trigger Link</th>
                                        <th class="py-2">Logged Query Input</th>
                                    </tr>
                                </thead>
                                <tbody id="logsTableBody" class="divide-y divide-slate-900 text-slate-300 mono">
                                    <!-- Sync records streams -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>
        </div>

        <script>
            let currentScopeMode = 'all';
            let globalToolsList = [];

            document.getElementById('keyExpiry').value = new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0];

            async function attemptLogin() {
                const username = document.getElementById('admUser').value;
                const password = document.getElementById('admPass').value;
                
                const res = await fetch('/api/admin/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username, password })
                });

                if (res.ok) {
                    document.getElementById('loginView').classList.add('hidden');
                    document.getElementById('appView').classList.remove('hidden');
                    refreshTelemetry();
                    setInterval(refreshTelemetry, 3500); 
                } else {
                    document.getElementById('loginErr').classList.remove('hidden');
                }
            }

            function setScopeMode(mode) {
                currentScopeMode = mode;
                const allBtn = document.getElementById('toolScopeAll');
                const specBtn = document.getElementById('toolScopeSpec');
                const grid = document.getElementById('specificToolsGrid');

                if(mode === 'all') {
                    allBtn.className = "flex-1 py-1.5 rounded-lg text-xs font-bold border border-indigo-500 bg-indigo-500/10 text-indigo-400";
                    specBtn.className = "flex-1 py-1.5 rounded-lg text-xs font-bold border border-slate-800 bg-[#121324] text-slate-400";
                    grid.classList.add('hidden');
                } else {
                    specBtn.className = "flex-1 py-1.5 rounded-lg text-xs font-bold border border-indigo-500 bg-indigo-500/10 text-indigo-400";
                    allBtn.className = "flex-1 py-1.5 rounded-lg text-xs font-bold border border-slate-800 bg-[#121324] text-slate-400";
                    grid.classList.remove('hidden');
                }
            }

            function toggleEndpoints() {
                document.getElementById('endpointsDrawer').classList.toggle('hidden');
            }

            function copyToClipboard(text) {
                navigator.clipboard.writeText(text);
                alert("Copied Target Proxy Route Path.");
            }

            async function refreshTelemetry() {
                const res = await fetch('/api/admin/data');
                const data = await res.json();
                globalToolsList = data.tools;
                
                const grid = document.getElementById('specificToolsGrid');
                if(!grid.children.length) {
                    grid.innerHTML = data.tools.map(t => `
                        <label class="flex items-center gap-2 p-1.5 rounded border border-slate-900 bg-[#070810] text-[11px] text-slate-300 cursor-pointer hover:border-slate-800">
                            <input type="checkbox" value="${t.id}" class="accent-indigo-500">
                            <span class="truncate">${t.name}</span>
                        </label>
                    `).join('');
                }

                const rawList = document.getElementById('rawUrlsList');
                const hostUrl = window.location.origin;
                rawList.innerHTML = data.tools.map(t => `
                    <div onclick="copyToClipboard('${hostUrl}/gateway/${t.id}?key=YOUR_KEY&${t.param}=')" class="p-2.5 bg-[#07080f] border border-slate-800 hover:border-indigo-500/50 rounded-xl cursor-pointer text-xs truncate transition-all font-mono">
                        <span class="text-indigo-400 font-bold">[${t.id.toUpperCase()}]</span><br>
                        <span class="text-slate-400">${hostUrl}/gateway/${t.id}</span>
                    </div>
                `).join('');

                const keysContainer = document.getElementById('keysContainer');
                if(data.keys.length === 0) {
                    keysContainer.innerHTML = `<p class="text-xs text-slate-500 py-4 text-center mono">No configured validation signatures found.</p>`;
                } else {
                    keysContainer.innerHTML = data.keys.map(k => {
                        const statusColor = k.status === 'active' ? 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5' : 'text-rose-400 border-rose-500/20 bg-rose-500/5';
                        return `
                        <div class="p-4 bg-[#0a0b14] border border-slate-900 rounded-xl space-y-3">
                            <div class="flex items-start justify-between">
                                <div>
                                    <h4 class="font-bold text-sm text-white">${k.name}</h4>
                                    <p class="text-xs font-mono text-indigo-300 select-all bg-[#111222] px-2 py-0.5 rounded border border-slate-800 inline-block mt-1">${k.key}</p>
                                </div>
                                <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${statusColor}">${k.status}</span>
                            </div>
                            <div class="grid grid-cols-3 gap-2 text-[11px] text-slate-400 mono">
                                <div>Counter: <span class="text-white font-bold">${k.uses} / ${k.limit}</span></div>
                                <div>Expires: <span class="text-white font-bold">${k.expiry}</span></div>
                                <span class="truncate">Scope: ${k.tools.join(', ')}</span>
                            </div>
                            <div class="flex flex-wrap gap-1.5 pt-1 border-t border-slate-900/40">
                                <button onclick="keyAction('${k.key}', 'restart_limit')" class="text-[10px] bg-slate-900 border border-slate-800 text-slate-300 px-2 py-1 rounded hover:bg-slate-800">Reset Count</button>
                                ${k.status === 'active' ? 
                                    `<button onclick="keyAction('${k.key}', 'suspend')" class="text-[10px] bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2 py-1 rounded hover:bg-amber-500/20">Suspend</button>` :
                                    `<button onclick="keyAction('${k.key}', 'activate')" class="text-[10px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-2 py-1 rounded hover:bg-emerald-500/20">Activate</button>`
                                }
                                <button onclick="promptEdit('${k.key}', ${k.limit}, '${k.expiry}')" class="text-[10px] bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-2 py-1 rounded hover:bg-indigo-500/20">Edit Parameters</button>
                                <button onclick="keyAction('${k.key}', 'delete')" class="text-[10px] bg-rose-500/10 border border-rose-500/20 text-rose-400 px-2 py-1 rounded hover:bg-rose-500/20 ml-auto">Delete</button>
                            </div>
                        </div>
                        `;
                    }).join('');
                }

                const logsBody = document.getElementById('logsTableBody');
                if(data.logs.length === 0) {
                    logsBody.innerHTML = `<tr><td colspan="4" class="py-4 text-center text-slate-600">Waiting for requests...</td></tr>`;
                } else {
                    logsBody.innerHTML = data.logs.reverse().map(l => `
                        <tr>
                            <td class="py-2 text-slate-500">${l.timestamp}</td>
                            <td class="py-2 text-slate-300 font-semibold">${l.key_name}</td>
                            <td class="py-2 text-indigo-400 font-bold">[${l.tool.toUpperCase()}]</td>
                            <td class="py-2 text-slate-400">${l.query}</td>
                        </tr>
                    `).join('');
                }
            }

            async function generateKey() {
                const key_name = document.getElementById('keyName').value;
                const custom_key = document.getElementById('keyString').value;
                const daily_limit = parseInt(document.getElementById('keyLimit').value);
                const expiry_date = document.getElementById('keyExpiry').value;

                if(!key_name || !custom_key) return alert("Fill in token settings.");

                let allowed_tools = ['all'];
                if(currentScopeMode === 'spec') {
                    const checked = Array.from(document.querySelectorAll('#specificToolsGrid input:checked')).map(el => el.value);
                    if(checked.length === 0) return alert("Select at least one validation tool pipeline mapping.");
                    allowed_tools = checked;
                }

                const res = await fetch('/api/admin/keys', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ key_name, custom_key, daily_limit, expiry_date, allowed_tools })
                });

                if(res.ok) {
                    document.getElementById('keyName').value = '';
                    document.getElementById('keyString').value = '';
                    refreshTelemetry();
                } else {
                    const err = await res.json();
                    alert(err.detail || "Key collision detected.");
                }
            }

            async function keyAction(keyId, actionType) {
                await fetch(`/api/admin/keys/${keyId}/action`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ type: actionType })
                });
                refreshTelemetry();
            }

            function promptEdit(keyId, oldLimit, oldExpiry) {
                const newLimit = prompt("New Request Threshold Limit Max count:", oldLimit);
                if (newLimit === null) return;
                const newExpiry = prompt("New expiry deadline date (YYYY-MM-DD):", oldExpiry);
                if (newExpiry === null) return;

                fetch(`/api/admin/keys/${keyId}/action`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ type: 'edit', limit: parseInt(newLimit), expiry: newExpiry })
                }).then(() => refreshTelemetry());
            }
        </script>
    </body>
    </html>
    """
