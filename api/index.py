import datetime
import httpx
from typing import Dict, List, Optional
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="SHAYAN_EXPLORER API Gateway")

# Global Config
ADMIN_USER = "vernex"
ADMIN_PASS = "vernex@16vx"
BASE_TARGET_URL = "https://ft-osint-api.duckdns.org/api"
DEFAULT_UPSTREAM_KEY = "vernex-6a9dc4fdd5923c40b0aba27bf1e39e3f"

# In-Memory Database (Will clear on Vercel spin-down; connect a free MongoDB/KV for production permanence)
api_keys_db: Dict[str, dict] = {}
search_logs: List[dict] = []

# Available Tools Catalog
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
]

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class KeyGenRequest(BaseModel):
    key_name: str
    custom_key: str
    daily_limit: int
    expiry_date: str  # YYYY-MM-DD
    allowed_tools: List[str]  # ["all"] or specific IDs

# --- REVERSE PROXY GATEWAY ROUTE ---
@app.get("/gateway/{tool_id}")
async def gateway_router(tool_id: str, request: Request):
    query_params = dict(request.query_params)
    user_key = query_params.get("key")
    
    if not user_key or user_key not in api_keys_db:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    key_data = api_keys_db[user_key]
    
    # Check Suspension
    if key_data["status"] == "suspended":
        raise HTTPException(status_code=403, detail="API Key is suspended")
        
    # Check Expiry
    expiry = datetime.datetime.strptime(key_data["expiry"], "%Y-%m-%d").date()
    if datetime.date.today() > expiry:
        raise HTTPException(status_code=403, detail="API Key has expired")
        
    # Check Limit
    if key_data["uses"] >= key_data["limit"]:
        raise HTTPException(status_code=429, detail="API Key request limit reached")
        
    # Check Tool Permissions
    if "all" not in key_data["tools"] and tool_id not in key_data["tools"]:
        raise HTTPException(status_code=403, detail="This key is not authorized to use this specific tool")

    # Find the parameter name for logging
    tool_config = next((t for t in TOOLS_LIST if t["id"] == tool_id), None)
    search_query = "Unknown Query"
    if tool_config:
        search_query = query_params.get(tool_config["param"], "N/A")

    # Log the search
    search_logs.append({
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "key_name": key_data["name"],
        "key": user_key,
        "tool": tool_id,
        "query": search_query
    })
    
    # Increment Usage
    key_data["uses"] += 1
    
    # Forward to Upstream API safely
    target_tool = next((t for t in TOOLS_LIST if t["id"] == tool_id), None)
    if not target_tool:
        raise HTTPException(status_code=404, detail="Tool Endpoint Not Found")
        
    forward_params = query_params.copy()
    forward_params["key"] = DEFAULT_UPSTREAM_KEY # Inject master key silently
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_TARGET_URL}/{tool_id}", params=forward_params, timeout=10.0)
            return JSONResponse(status_code=response.status_code, content=response.json())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": "Upstream error or timeout", "details": str(e)})

# --- ADMIN API ENDPOINTS ---
@app.post("/api/admin/login")
def admin_login(data: LoginRequest):
    if data.username == ADMIN_USER and data.password == ADMIN_PASS:
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/admin/data")
def get_admin_data():
    return {
        "keys": list(api_keys_db.values()),
        "logs": search_logs[-100:],  # Return last 100 entries
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

# --- RENDER FRONTEND ---
@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SHAYAN_EXPLORER // CENTRAL API COMMAND</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;800&family=Space+Grotesk:wght@400;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #050508; }
            .mono { font-family: 'Space Grotesk', sans-serif; }
            .glow-border { border: 1px solid rgba(139, 92, 246, 0.2); box-shadow: 0 0 15px rgba(139, 92, 246, 0.05); }
            .glow-border:hover { border-color: rgba(139, 92, 246, 0.6); box-shadow: 0 0 20px rgba(139, 92, 246, 0.2); }
            .cyber-badge { background: linear-gradient(90deg, #c084fc, #6366f1); }
        </style>
    </head>
    <body class="text-slate-100 min-h-screen selection:bg-indigo-500 selection:text-white">

        <!-- LOGIN MODAL -->
        <div id="loginView" class="fixed inset-0 bg-[#050508] z-50 flex items-center justify-center p-4">
            <div class="w-full max-w-md bg-[#0b0c14] border border-slate-800 rounded-2xl p-8 shadow-2xl">
                <div class="mb-8 text-center">
                    <span class="text-xs uppercase tracking-widest text-indigo-400 font-bold mono">Secure Gateway v4.0</span>
                    <h1 class="text-3xl font-extrabold text-white mt-1">SHAYAN_EXPLORER</h1>
                </div>
                <div class="space-y-4">
                    <div>
                        <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1 font-semibold">Admin Identity</label>
                        <input id="admUser" type="text" class="w-full bg-[#121424] border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition-all" placeholder="Enter identity ID">
                    </div>
                    <div>
                        <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1 font-semibold">Passphrase</label>
                        <input id="admPass" type="password" class="w-full bg-[#121424] border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition-all" placeholder="••••••••">
                    </div>
                    <button onclick="attemptLogin()" class="w-full bg-indigo-600 hover:bg-indigo-500 active:scale-[0.99] text-white font-semibold py-3 px-4 rounded-xl transition-all shadow-lg shadow-indigo-600/20 mt-2">
                        Initialize Terminal
                    </button>
                    <p id="loginErr" class="text-xs text-rose-400 mt-2 hidden text-center mono">Authentication failure. Vector denied.</p>
                </div>
            </div>
        </div>

        <!-- MAIN TERMINAL APP -->
        <div id="appView" class="hidden min-h-screen flex flex-col">
            <!-- Top Navigation Banner -->
            <header class="border-b border-slate-900 bg-[#07080f]/80 backdrop-blur-md sticky top-0 z-40 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
                <div class="flex items-center gap-3">
                    <div class="h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></div>
                    <span class="font-bold tracking-tight text-lg text-white">SHAYAN_EXPLORER <span class="text-indigo-400 text-xs px-2 py-0.5 rounded border border-indigo-500/20 bg-indigo-500/5 ml-1">ADMIN CONTROL</span></span>
                </div>
                
                <div class="flex items-center gap-3">
                    <button onclick="toggleEndpoints()" class="text-xs font-semibold px-4 py-2 bg-[#111322] border border-slate-800 hover:border-slate-700 rounded-xl transition-all">
                        📋 View Raw Endpoints (No Key)
                    </button>
                </div>
            </header>

            <!-- RAW ENDPOINTS ACCORDION -->
            <div id="endpointsDrawer" class="hidden bg-[#0a0b12] border-b border-slate-900 p-6">
                <div class="max-w-7xl mx-auto">
                    <h3 class="text-sm font-bold uppercase tracking-wider text-indigo-400 mb-3 mono">Available Proxy Endpoints (Click URL to copy)</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" id="rawUrlsList"></div>
                </div>
            </div>

            <main class="flex-1 p-6 max-w-7xl w-full mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Left Dashboard: Management Interface -->
                <div class="lg:col-span-1 space-y-6">
                    <!-- Key Provisioning Container -->
                    <div class="bg-[#070810] border border-slate-900 rounded-2xl p-6">
                        <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <span>🔑</span> Provision API Key
                        </h2>
                        <div class="space-y-4">
                            <div>
                                <label class="block text-xs uppercase text-slate-400 mb-1 font-semibold">Key Identifier / Name</label>
                                <input id="keyName" type="text" placeholder="e.g., Premium User Client" class="w-full bg-[#111322] border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-xs uppercase text-slate-400 mb-1 font-semibold">Custom Dynamic Key</label>
                                <input id="keyString" type="text" placeholder="e.g., client-xyz-2026" class="w-full bg-[#111322] border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                            </div>
                            <div class="grid grid-cols-2 gap-3">
                                <div>
                                    <label class="block text-xs uppercase text-slate-400 mb-1 font-semibold">Request Limit</label>
                                    <input id="keyLimit" type="number" value="1000" class="w-full bg-[#111322] border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                                </div>
                                <div>
                                    <label class="block text-xs uppercase text-slate-400 mb-1 font-semibold">Expiry Date</label>
                                    <input id="keyExpiry" type="date" class="w-full bg-[#111322] border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                                </div>
                            </div>
                            
                            <div>
                                <label class="block text-xs uppercase text-slate-400 mb-2 font-semibold">Scope Restrictions</label>
                                <div class="flex gap-2 mb-3">
                                    <button id="toolScopeAll" onclick="setScopeMode('all')" class="flex-1 py-1.5 rounded-lg text-xs font-bold border border-indigo-500 bg-indigo-500/10 text-indigo-400">All Tools</button>
                                    <button id="toolScopeSpec" onclick="setScopeMode('spec')" class="flex-1 py-1.5 rounded-lg text-xs font-bold border border-slate-800 bg-[#111322] text-slate-400">Specific Select</button>
                                </div>
                                <div id="specificToolsGrid" class="hidden grid grid-cols-2 gap-2 max-h-40 overflow-y-auto p-2 bg-[#0c0d17] rounded-xl border border-slate-900">
                                    <!-- Populated programmatically -->
                                </div>
                            </div>

                            <button onclick="generateKey()" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 px-4 rounded-xl text-sm transition-all shadow-lg mt-2">
                                Authorize Key Allocation
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Right Dashboard: Active Assets & Key Logs -->
                <div class="lg:col-span-2 space-y-6">
                    <!-- Keys Management List -->
                    <div class="bg-[#070810] border border-slate-900 rounded-2xl p-6">
                        <h2 class="text-lg font-bold text-white mb-4">Active System Allocations</h2>
                        <div class="space-y-3 max-h-[400px] overflow-y-auto pr-1" id="keysContainer">
                            <!-- Keys populated dynamically -->
                        </div>
                    </div>

                    <!-- Live Query Inspection Stream -->
                    <div class="bg-[#070810] border border-slate-900 rounded-2xl p-6">
                        <h2 class="text-lg font-bold text-white mb-4 flex items-center justify-between">
                            <span>📋 Vector Search Telemetry Logs</span>
                            <span class="text-xs uppercase bg-[#111322] border border-slate-800 px-3 py-1 rounded-full text-slate-400 mono">Real-Time Sync</span>
                        </h2>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-xs">
                                <thead>
                                    <tr class="border-b border-slate-900 text-slate-400 font-mono">
                                        <th class="py-2">Timestamp</th>
                                        <th class="py-2">Key Label</th>
                                        <th class="py-2">Tool Executed</th>
                                        <th class="py-2">Target Query</th>
                                    </tr>
                                </thead>
                                <tbody id="logsTableBody" class="divide-y divide-slate-900 text-slate-300 mono">
                                    <!-- Logs items populate here -->
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

            // Set default date for calendar entry
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
                    setInterval(refreshTelemetry, 4000); // Polling update metrics loop
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
                    specBtn.className = "flex-1 py-1.5 rounded-lg text-xs font-bold border border-slate-800 bg-[#111322] text-slate-400";
                    grid.classList.add('hidden');
                } else {
                    specBtn.className = "flex-1 py-1.5 rounded-lg text-xs font-bold border border-indigo-500 bg-indigo-500/10 text-indigo-400";
                    allBtn.className = "flex-1 py-1.5 rounded-lg text-xs font-bold border border-slate-800 bg-[#111322] text-slate-400";
                    grid.classList.remove('hidden');
                }
            }

            function toggleEndpoints() {
                const drawer = document.getElementById('endpointsDrawer');
                drawer.classList.toggle('hidden');
            }

            function copyToClipboard(text) {
                navigator.clipboard.writeText(text);
                alert("Copied Endpoint Target Route successfully.");
            }

            async function refreshTelemetry() {
                const res = await fetch('/api/admin/data');
                const data = await res.json();
                
                globalToolsList = data.tools;
                
                // Populate Tools Checkbox Grid if empty
                const grid = document.getElementById('specificToolsGrid');
                if(!grid.children.length) {
                    grid.innerHTML = data.tools.map(t => `
                        <label class="flex items-center gap-2 p-1.5 rounded border border-slate-900 bg-[#070810] text-[11px] text-slate-300 cursor-pointer hover:border-slate-800">
                            <input type="checkbox" value="${t.id}" class="accent-indigo-500">
                            <span class="truncate">${t.name}</span>
                        </label>
                    `).join('');
                }

                // Render Raw URLs Header list
                const rawList = document.getElementById('rawUrlsList');
                const hostUrl = window.location.origin;
                rawList.innerHTML = data.tools.map(t => `
                    <div onclick="copyToClipboard('${hostUrl}/gateway/${t.id}?key=YOUR_KEY&${t.param}=')" class="p-2.5 bg-[#07080f] border border-slate-800 hover:border-indigo-500/50 rounded-xl cursor-pointer text-xs truncate transition-all font-mono">
                        <span class="text-indigo-400 font-bold">[${t.id.toUpperCase()}]</span><br>
                        <span class="text-slate-400">${hostUrl}/gateway/${t.id}</span>
                    </div>
                `).join('');

                // Render Keys
                const keysContainer = document.getElementById('keysContainer');
                if(data.keys.length === 0) {
                    keysContainer.innerHTML = `<p class="text-xs text-slate-500 py-4 text-center mono">No active token systems configured.</p>`;
                } else {
                    keysContainer.innerHTML = data.keys.map(k => {
                        const statusColor = k.status === 'active' ? 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5' : 'text-rose-400 border-rose-500/20 bg-rose-500/5';
                        return `
                        <div class="p-4 bg-[#0a0b12] border border-slate-900 rounded-xl space-y-3">
                            <div class="flex items-start justify-between">
                                <div>
                                    <h4 class="font-bold text-sm text-white">${k.name}</h4>
                                    <p class="text-xs font-mono text-indigo-300 select-all bg-[#111322] px-2 py-0.5 rounded border border-slate-800 inline-block mt-1">${k.key}</p>
                                </div>
                                <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${statusColor}">${k.status}</span>
                            </div>
                            <div class="grid grid-cols-3 gap-2 text-[11px] text-slate-400 mono">
                                <div>Usage: <span class="text-white font-bold">${k.uses} / ${k.limit}</span></div>
                                <div>Expiry: <span class="text-white font-bold">${k.expiry}</span></div>
                                <span class="truncate">Scope: ${k.tools.join(', ')}</span>
                            </div>
                            <div class="flex flex-wrap gap-1.5 pt-1 border-t border-slate-900/50">
                                <button onclick="keyAction('${k.key}', 'restart_limit')" class="text-[10px] bg-slate-900 border border-slate-800 text-slate-300 px-2 py-1 rounded hover:bg-slate-800">Reset Limit</button>
                                ${k.status === 'active' ? 
                                    `<button onclick="keyAction('${k.key}', 'suspend')" class="text-[10px] bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2 py-1 rounded hover:bg-amber-500/20">Suspend</button>` :
                                    `<button onclick="keyAction('${k.key}', 'activate')" class="text-[10px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-2 py-1 rounded hover:bg-emerald-500/20">Activate</button>`
                                }
                                <button onclick="promptEdit('${k.key}', ${k.limit}, '${k.expiry}')" class="text-[10px] bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-2 py-1 rounded hover:bg-indigo-500/20">Edit Parameters</button>
                                <button onclick="keyAction('${k.key}', 'delete')" class="text-[10px] bg-rose-500/10 border border-rose-500/20 text-rose-400 px-2 py-1 rounded hover:bg-rose-500/20 ml-auto">Terminate</button>
                            </div>
                        </div>
                        `;
                    }).join('');
                }

                // Render Logs
                const logsBody = document.getElementById('logsTableBody');
                if(data.logs.length === 0) {
                    logsBody.innerHTML = `<tr><td colspan="4" class="py-4 text-center text-slate-600">No active operational logs.</td></tr>`;
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

                if(!key_name || !custom_key) return alert("Provide label and payload signature configurations.");

                let allowed_tools = ['all'];
                if(currentScopeMode === 'spec') {
                    const checked = Array.from(document.querySelectorAll('#specificToolsGrid input:checked')).map(el => el.value);
                    if(checked.length === 0) return alert("Select at least one active API pipeline authorization.");
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
                    alert(err.detail || "Allocation pipeline clash.");
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
                const newLimit = prompt("Set new Total Request Allocation Limit:", oldLimit);
                if (newLimit === null) return;
                const newExpiry = prompt("Set new system expiration format (YYYY-MM-DD):", oldExpiry);
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
