import os
import secrets
import requests
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
from dateutil import parser

app = Flask(__name__)

TARGET_API_BASE = "https://ft-osint-api.duckdns.org/api"
UPSTREAM_DEFAULT_KEY = "vernex-6a9dc4fdd5923c40b0aba27bf1e39e3f"

# इन-मेमरी डेटाबेस जो री-हाइड्रेशन फॉलबैक के साथ काम करता है
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

# यहाँ पूरे 28 APIs को लिस्ट में जोड़ दिया गया है
SUPPORTED_TOOLS = [
    "adv", "paytm", "imei", "calltracer", "upi", "ifsc", 
    "number", "pincode", "ip", "challan", "ff", "bgmi", 
    "snap", "email", "vehicle", "git", "insta", "tg", 
    "tgidinfo", "numleak", "pan", "adharfamily", "aadhar",
    "veh2num", "bomber", "pk", "passport", "driving", "voter"
]

# --- QUANTUM DASHBOARD UI TEMPLATE ---
HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SHAYAN_EXPLORER | Quantum Enterprise Gateway Hub</title>
    <script src="https://cdn.jsdelivr.net/npm/feather-icons/dist/feather.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: radial-gradient(circle at top right, #0c071e, #020105); color: #f3f4f6; }
        .glass { background: rgba(18, 11, 36, 0.65); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.06); }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); }
        ::-webkit-scrollbar-thumb { background: rgba(147, 51, 234, 0.3); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(147, 51, 234, 0.6); }
    </style>
</head>
<body class="min-h-screen antialiased font-sans pb-12">

    <header class="border-b border-white/5 py-4 px-6 flex flex-wrap justify-between items-center bg-black/40 backdrop-blur-md sticky top-0 z-40 gap-4">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/20">
                <i data-feather="activity" class="w-5 h-5 text-white"></i>
            </div>
            <div>
                <span class="text-lg font-black tracking-wider text-white block">SHAYAN_EXPLORER</span>
                <div class="flex items-center space-x-1.5">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-ping"></span>
                    <span class="text-[10px] text-emerald-400 font-bold uppercase tracking-widest">Gateway Engine Operational</span>
                </div>
            </div>
        </div>
        
        <div class="flex items-center space-x-6 bg-black/30 px-4 py-1.5 rounded-xl border border-white/5 text-xs">
            <div class="text-center">
                <span class="text-gray-400 block text-[9px] uppercase font-bold">Total Key Registry</span>
                <span id="statTotalKeys" class="font-mono text-purple-400 font-bold">1</span>
            </div>
            <div class="w-px h-6 bg-white/10"></div>
            <div class="text-center">
                <span class="text-gray-400 block text-[9px] uppercase font-bold">Success Stream</span>
                <span id="statSuccess" class="font-mono text-emerald-400 font-bold">0</span>
            </div>
            <div class="w-px h-6 bg-white/10"></div>
            <div class="text-center">
                <span class="text-gray-400 block text-[9px] uppercase font-bold">Failed Block</span>
                <span id="statFailed" class="font-mono text-rose-400 font-bold">0</span>
            </div>
        </div>

        <div class="flex items-center space-x-2">
            <button onclick="toggleModal(true)" class="px-4 py-2 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 rounded-xl border border-purple-500/20 text-xs font-bold tracking-wide flex items-center space-x-2 transition">
                <i data-feather="code" class="w-4 h-4"></i> <span>API Routes Guide</span>
            </button>
            <button onclick="syncClientToServerFallback()" class="p-2 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/5 rounded-xl transition" title="Force State Sync">
                <i data-feather="refresh-cw" class="w-4 h-4"></i>
            </button>
        </div>
    </header>

    <main class="max-w-7xl mx-auto p-4 md:p-6 space-y-6 mt-2">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            <div class="lg:col-span-1 space-y-6">
                <div class="glass rounded-2xl p-6 flex flex-col space-y-4 shadow-xl">
                    <div class="flex justify-between items-center border-b border-white/5 pb-2">
                        <h2 id="formTitle" class="text-xs font-black tracking-wider text-purple-400 uppercase flex items-center">
                            <i data-feather="plus-circle" class="mr-2 w-4 h-4"></i> Provision Token Strategy
                        </h2>
                        <button type="button" onclick="generateRandomKey()" class="text-[10px] text-indigo-400 font-bold hover:underline flex items-center space-x-1">
                            <i data-feather="key" class="w-3 h-3"></i> <span>Auto Generate Key</span>
                        </button>
                    </div>
                    
                    <form id="keyForm" class="space-y-4">
                        <div>
                            <label class="block text-[10px] uppercase text-gray-400 font-bold mb-1">User Identifier Profile</label>
                            <input type="text" id="clientName" placeholder="Client Label / Company" class="w-full bg-black/40 border border-white/10 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-purple-500 transition" required>
                        </div>
                        <div>
                            <label class="block text-[10px] uppercase text-gray-400 font-bold mb-1">Unique API Token Target Signature</label>
                            <input type="text" id="apiKey" placeholder="SHAYAN-SECRET-CODE" class="w-full bg-black/40 border border-white/10 rounded-xl p-2.5 text-xs font-mono text-purple-300 focus:outline-none focus:border-purple-500 transition" required>
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="block text-[10px] uppercase text-gray-400 font-bold mb-1">Quota Pool Limit</label>
                                <input type="number" id="keyLimit" value="500" class="w-full bg-black/40 border border-white/10 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-purple-500 transition" required>
                            </div>
                            <div>
                                <label class="block text-[10px] uppercase text-gray-400 font-bold mb-1">Expiration Context</label>
                                <input type="datetime-local" id="keyExpire" value="2026-12-31T23:59" class="w-full bg-black/40 border border-white/10 rounded-xl p-2.5 text-xs font-mono text-white focus:outline-none focus:border-purple-500 transition" required>
                            </div>
                        </div>
                        <div>
                            <label class="block text-[10px] uppercase text-gray-400 font-bold mb-2">Scope Strategy Authorization Restrictions</label>
                            <div class="flex items-center space-x-2 mb-2 p-2 bg-purple-950/20 rounded-xl border border-purple-500/10">
                                <input type="checkbox" id="allToolsCheck" checked onchange="toggleAllTools(this)" class="accent-purple-600">
                                <label for="allToolsCheck" class="text-[11px] font-bold text-emerald-400 cursor-pointer">Grant Global Authorization (All Tools)</label>
                            </div>
                            <div id="toolsGrid" class="grid grid-cols-2 gap-1.5 max-h-32 overflow-y-auto p-1 opacity-40 pointer-events-none transition"></div>
                        </div>
                        <div class="flex space-x-2 pt-2">
                            <button type="button" id="cancelEditBtn" onclick="resetFormState()" class="hidden w-1/3 py-2.5 bg-white/5 hover:bg-white/10 text-gray-400 rounded-xl font-bold text-xs transition">Cancel</button>
                            <button type="submit" id="submitBtn" class="flex-1 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-xl font-bold text-xs tracking-wider transition shadow-lg shadow-purple-600/20">PROVISION ACCESS</button>
                        </div>
                    </form>
                </div>

                <div class="glass rounded-2xl p-4 shadow-xl space-y-3">
                    <h3 class="text-xs font-black tracking-wider text-indigo-400 uppercase flex items-center"><i data-feather="terminal" class="w-3.5 h-3.5 mr-1.5"></i> Live API Query Sandbox</h3>
                    <div class="space-y-2 text-xs">
                        <select id="sandboxTool" class="w-full bg-black/40 border border-white/10 rounded-xl p-2 text-gray-300 focus:outline-none focus:border-indigo-500"></select>
                        <input type="text" id="sandboxKey" placeholder="Enter Valid API Key Token" class="w-full bg-black/40 border border-white/10 rounded-xl p-2 font-mono text-purple-300">
                        <input type="text" id="sandboxParam" placeholder="Value (e.g. Mobile, PAN, UID)" class="w-full bg-black/40 border border-white/10 rounded-xl p-2">
                        <button onclick="runSandboxTest()" class="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold transition text-[11px]">FIRE SANDBOX DATA ROUTE</button>
                    </div>
                </div>
            </div>

            <div class="lg:col-span-2 glass rounded-2xl p-6 flex flex-col max-h-[640px] shadow-xl">
                <div class="flex flex-wrap justify-between items-center mb-4 gap-2">
                    <h2 class="text-xs font-black uppercase tracking-wider text-indigo-400 flex items-center"><i data-feather="shield" class="w-4 h-4 mr-2"></i> Runtime System Database Matrix</h2>
                    <button onclick="clearAllSystemKeys()" class="text-[10px] bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 px-2 py-1 rounded-lg font-bold transition">Wipe Custom Registry</button>
                </div>
                
                <div class="overflow-x-auto flex-1 overflow-y-auto">
                    <table class="w-full text-left text-xs border-collapse">
                        <thead class="sticky top-0 bg-[#120b24] z-10 text-gray-400 font-bold uppercase tracking-wider border-b border-white/5">
                            <tr>
                                <th class="pb-3 pr-2">Profile ID</th>
                                <th class="pb-3 pr-2">Token Signature</th>
                                <th class="pb-3 pr-2">Scope Scope</th>
                                <th class="pb-3 pr-2">Quota Analytics Usage Meter</th>
                                <th class="pb-3 pr-2">Expiration</th>
                                <th class="pb-3 pr-2">Status</th>
                                <th class="pb-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="keysTable" class="divide-y divide-white/5 font-mono text-gray-300"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="glass rounded-2xl p-6 shadow-xl">
            <div class="flex flex-wrap justify-between items-center mb-4 gap-3">
                <h2 class="text-xs font-black uppercase tracking-wider text-blue-400 flex items-center"><i data-feather="activity" class="w-4 h-4 mr-2"></i> System Request Streaming Audit Buffer Logs</h2>
                <div class="flex items-center space-x-2 w-full sm:w-auto">
                    <input type="text" id="logSearchInput" onkeyup="filterLogRows()" placeholder="Search incoming logs..." class="bg-black/40 border border-white/10 rounded-xl px-3 py-1 text-xs text-gray-300 focus:outline-none focus:border-blue-500 w-full sm:w-48">
                    <button onclick="downloadLogsCSV()" class="bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 border border-blue-500/20 px-2 py-1 rounded-lg font-bold text-[10px] transition">Export CSV</button>
                    <button onclick="clearStreamingLogs()" class="bg-rose-600/10 hover:bg-rose-600/20 text-rose-400 border border-rose-500/20 px-2 py-1 rounded-lg font-bold text-[10px] transition">Wipe Log Stream</button>
                </div>
            </div>
            
            <div class="overflow-x-auto max-h-64 overflow-y-auto">
                <table id="mainLogsTable" class="w-full text-left text-xs border-collapse">
                    <thead class="sticky top-0 bg-[#0d071a] border-b border-white/10 text-gray-400 font-bold uppercase">
                        <tr>
                            <th class="py-2">Timestamp</th>
                            <th class="py-2">Client Label</th>
                            <th class="py-2">Token Value</th>
                            <th class="py-2">Route Target</th>
                            <th class="py-2">Param Metadata Queries</th>
                            <th class="py-2">Gateway Status</th>
                        </tr>
                    </thead>
                    <tbody id="logsTable" class="divide-y divide-white/5 font-mono text-gray-300"></tbody>
                </table>
            </div>
        </div>
    </main>

    <div id="sandboxModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">
        <div class="glass max-w-xl w-full rounded-2xl p-6 flex flex-col max-h-[80vh]">
            <div class="flex justify-between items-center mb-2 border-b border-white/5 pb-2">
                <span class="text-xs font-black text-indigo-400 uppercase flex items-center"><i data-feather="terminal" class="mr-2 w-4 h-4"></i> Sandbox Network Payload Response Object</span>
                <button onclick="document.getElementById('sandboxModal').classList.add('hidden')" class="text-gray-400 hover:text-white"><i data-feather="x"></i></button>
            </div>
            <pre id="sandboxPre" class="bg-black/50 border border-white/5 p-4 rounded-xl text-emerald-400 text-[11px] overflow-auto flex-1 font-mono"></pre>
        </div>
    </div>

    <div id="endpointModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">
        <div class="glass max-w-2xl w-full rounded-2xl p-6 flex flex-col max-h-[85vh]">
            <div class="flex justify-between items-center mb-4 border-b border-white/5 pb-2">
                <h3 class="font-black text-white tracking-wide text-xs uppercase flex items-center"><i data-feather="code" class="text-purple-400 mr-2 w-4 h-4"></i> Uniform Resource Interface Schema Dashboard</h3>
                <button onclick="toggleModal(false)" class="text-gray-400 hover:text-white"><i data-feather="x"></i></button>
            </div>
            <p class="text-[11px] text-gray-400 mb-4">Click any structural code component endpoint below to copy it directly to your clipboard storage.</p>
            <div id="modalList" class="space-y-2 overflow-y-auto flex-1 pr-1 font-mono text-[11px]"></div>
        </div>
    </div>

    <script>
        // यहाँ भी पूरे 28 टूल्स लिस्टेड हैं
        const toolsList = ["adv","paytm","imei","calltracer","upi","ifsc","number","pincode","ip","challan","ff","bgmi","snap","email","vehicle","git","insta","tg","tgidinfo","numleak","pan","adharfamily","aadhar","veh2num","bomber","pk","passport","driving","voter"];
        let localKeysCache = {};

        function initLocalStorageBackup() {
            if(!localStorage.getItem('SHAYAN_BACKED_KEYS')) {
                const defaultPool = {
                    "SHAYAN-MASTER": { "name": "Master Enterprise Dev", "key": "SHAYAN-MASTER", "expire_date": "2026-12-31T23:59", "limit": 1000, "used": 0, "status": "Active", "tools": ["all"] }
                };
                localStorage.setItem('SHAYAN_BACKED_KEYS', JSON.stringify(defaultPool));
            }
        }

        async function syncClientToServerFallback() {
            initLocalStorageBackup();
            const localPool = JSON.parse(localStorage.getItem('SHAYAN_BACKED_KEYS') || '{}');
            
            try {
                await fetch('/api/admin/keys/sync', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ keys: Object.values(localPool) })
                });
            } catch(err) { console.error("Sync Failure Intercepted: ", err); }
            
            fetchState();
        }

        function generateRandomKey() {
            const hex = 'SHAYAN-' + Array.from({length:16}, () => Math.floor(Math.random()*16).toString(16)).join('').toUpperCase();
            document.getElementById('apiKey').value = hex;
        }

        function initToolsCheckboxes() {
            const grid = document.getElementById('toolsGrid');
            const sandboxSelect = document.getElementById('sandboxTool');
            grid.innerHTML = ''; sandboxSelect.innerHTML = '';
            
            toolsList.forEach(t => {
                grid.innerHTML += `
                    <div class="flex items-center space-x-2 bg-black/20 p-1.5 rounded-xl border border-white/5 hover:border-white/10">
                        <input type="checkbox" value="${t}" id="chk-${t}" class="tool-chk accent-purple-600">
                        <label for="chk-${t}" class="text-[11px] tracking-wide text-gray-300 font-medium capitalize cursor-pointer select-none">${t}</label>
                    </div>`;
                sandboxSelect.innerHTML += `<option value="${t}" class="bg-[#120b24] capitalize">${t.toUpperCase()} Service Module</option>`;
            });
        }

        function toggleAllTools(src) {
            const grid = document.getElementById('toolsGrid');
            if(src.checked) { grid.classList.add('opacity-40', 'pointer-events-none'); } 
            else { grid.classList.remove('opacity-40', 'pointer-events-none'); }
        }

        function toggleModal(open) {
            const modal = document.getElementById('endpointModal');
            modal.style.display = open ? 'flex' : 'none';
            if(open) {
                const host = window.location.origin;
                const list = document.getElementById('modalList');
                list.innerHTML = '';
                toolsList.forEach(t => {
                    let sampleParam = "num=9876543210";
                    if(t === 'email') sampleParam = "email=test@gmail.com";
                    else if(t === 'vehicle' || t === 'veh2num') sampleParam = "vehicle=MH02";
                    else if(t === 'pan') sampleParam = "pan=ANXPV7978A";
                    
                    const sampleUrl = `${host}/api/${t}?key=YOUR_KEY&${sampleParam}`;
                    list.innerHTML += `
                        <div onclick="copyText('${sampleUrl}')" class="p-2.5 bg-black/40 hover:bg-purple-600/10 border border-white/5 hover:border-purple-500/30 rounded-xl cursor-pointer transition flex justify-between items-center group">
                            <span class="text-purple-300 truncate mr-2">${sampleUrl}</span>
                            <i data-feather="copy" class="w-3.5 h-3.5 text-gray-500 group-hover:text-purple-400 flex-shrink-0"></i>
                        </div>`;
                });
                feather.replace();
            }
        }

        function copyText(txt) {
            navigator.clipboard.writeText(txt);
            alert("Endpoint string copied successfully.");
        }

        async function fetchState() {
            const res = await fetch('/api/admin/keys');
            const data = await res.json();
            
            const clientBackupPool = JSON.parse(localStorage.getItem('SHAYAN_BACKED_KEYS') || '{}');
            data.forEach(k => { clientBackupPool[k.key] = k; });
            localStorage.setItem('SHAYAN_BACKED_KEYS', JSON.stringify(clientBackupPool));

            const finalRenderPool = Object.values(clientBackupPool);
            document.getElementById('statTotalKeys').innerText = finalRenderPool.length;

            const table = document.getElementById('keysTable');
            table.innerHTML = '';
            localKeysCache = {};

            finalRenderPool.forEach(k => {
                localKeysCache[k.key] = k;
                const isAll = k.tools.includes('all');
                const badge = isAll ? 'GLOBAL' : `${k.tools.length} Tools`;
                const isSuspended = k.status === 'Suspended';
                const consumptionPercentage = Math.min(100, Math.round((k.used / k.limit) * 100) || 0);
                
                table.innerHTML += `
                    <tr class="hover:bg-white/5 transition ${isSuspended ? 'opacity-30' : ''}">
                        <td class="py-3 font-sans font-bold text-white pr-2">${k.name}</td>
                        <td class="py-3 text-purple-400 font-bold text-[11px] pr-2">${k.key}</td>
                        <td class="py-3 pr-2"><span class="px-2 py-0.5 rounded border text-[9px] font-bold ${isAll?'bg-emerald-500/10 text-emerald-400 border-emerald-500/20':'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'}">${badge}</span></td>
                        <td class="py-3 pr-2 w-32">
                            <div class="text-[10px] text-gray-400 mb-1 flex justify-between"><span>${k.used}/${k.limit}</span> <span>${consumptionPercentage}%</span></div>
                            <div class="w-full bg-white/10 h-1.5 rounded-full overflow-hidden">
                                <div class="bg-gradient-to-r from-purple-500 to-indigo-500 h-full" style="width: ${consumptionPercentage}%"></div>
                            </div>
                        </td>
                        <td class="py-3 text-gray-400 text-[11px] pr-2">${k.expire_date.replace('T', ' ')}</td>
                        <td class="py-3 pr-2"><span class="text-[10px] font-bold ${isSuspended?'text-rose-400':'text-emerald-400'}">${k.status.toUpperCase()}</span></td>
                        <td class="py-3 text-right space-x-1 whitespace-nowrap">
                            <button onclick="toggleSuspend('${k.key}', '${k.status}')" class="p-1.5 rounded hover:bg-white/5 text-amber-400 inline-block"><i data-feather="${isSuspended?'play':'square'}" class="w-3.5 h-3.5"></i></button>
                            <button onclick="triggerEdit('${k.key}')" class="p-1.5 rounded hover:bg-white/5 text-blue-400 inline-block"><i data-feather="edit-3" class="w-3.5 h-3.5"></i></button>
                            <button onclick="dropKey('${k.key}')" class="p-1.5 rounded hover:bg-white/5 text-rose-400 inline-block"><i data-feather="trash-2" class="w-3.5 h-3.5"></i></button>
                        </td>
                    </tr>`;
            });
            feather.replace();
        }

        async function fetchLogs() {
            const res = await fetch('/api/admin/logs');
            const data = await res.json();
            const table = document.getElementById('logsTable');
            
            let successfulLogsCount = 0;
            let failedLogsCount = 0;

            if(data.length === 0) {
                table.innerHTML = `<tr><td colspan="6" class="py-4 text-center text-gray-500 font-sans">Audit stream trace is currently empty.</td></tr>`;
                return;
            }

            table.innerHTML = '';
            data.forEach(l => {
                if(l.status === "Success") successfulLogsCount++; else failedLogsCount++;
                
                table.innerHTML += `
                    <tr class="hover:bg-white/5 transition log-row-item">
                        <td class="py-2 text-gray-500 text-[11px]">${l.timestamp}</td>
                        <td class="py-2 font-sans text-white">${l.key_name}</td>
                        <td class="py-2 text-purple-400">${l.key}</td>
                        <td class="py-2"><span class="px-1.5 py-0.5 bg-blue-500/10 text-blue-400 rounded border border-blue-500/20 text-[10px] font-bold">${l.tool}</span></td>
                        <td class="py-2 text-amber-300 max-w-[180px] truncate">${l.search}</td>
                        <td class="py-2"><span class="text-emerald-400 font-bold">${l.status}</span></td>
                    </tr>`;
            });
            
            document.getElementById('statSuccess').innerText = successfulLogsCount;
            document.getElementById('statFailed').innerText = failedLogsCount;
        }

        async function runSandboxTest() {
            const tool = document.getElementById('sandboxTool').value;
            const key = document.getElementById('sandboxKey').value;
            const param = document.getElementById('sandboxParam').value;
            if(!key || !param) return alert("Please fill up required inputs.");
            
            const localPool = JSON.parse(localStorage.getItem('SHAYAN_BACKED_KEYS') || '{}');
            if (localPool[key]) {
                await fetch('/api/admin/keys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(localPool[key])
                });
            }

            const url = `/api/${tool}?key=${key}&num=${param}&email=${param}&vehicle=${param}&pan=${param}`;
            document.getElementById('sandboxPre').innerText = "Querying live backend engine routes...";
            document.getElementById('sandboxModal').classList.remove('hidden');
            
            try {
                const r = await fetch(url);
                const d = await r.json();
                document.getElementById('sandboxPre').innerText = JSON.stringify(d, null, 4);
                
                if(d.status && d.status !== "error") {
                    if(localPool[key]) { localPool[key].used = (localPool[key].used || 0) + 1; }
                    localStorage.setItem('SHAYAN_BACKED_KEYS', JSON.stringify(localPool));
                }
            } catch(e) {
                document.getElementById('sandboxPre').innerText = "Exception Logged: " + e.toString();
            }
            fetchLogs();
            fetchState();
        }

        function filterLogRows() {
            const val = document.getElementById('logSearchInput').value.toLowerCase();
            document.querySelectorAll('.log-row-item').forEach(r => {
                r.style.display = r.innerText.toLowerCase().includes(val) ? '' : 'none';
            });
        }

        function downloadLogsCSV() {
            let csv = "Timestamp,Client Label,Token,Route Target,Query Search,Gateway Status\\n";
            document.querySelectorAll('.log-row-item').forEach(r => {
                const tds = Array.from(r.querySelectorAll('td')).map(td => td.innerText.replace(/,/g, ' '));
                if(tds.length > 0) csv += tds.join(',') + "\\n";
            });
            const blob = new Blob([csv], { type: 'text/csv' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `Gateway_Streaming_Audit_Logs.csv`;
            link.click();
        }

        function clearStreamingLogs() {
            if(confirm("Flush all logs memory?")) {
                fetch('/api/admin/logs', {method: 'POST'}).then(() => { fetchLogs(); });
            }
        }

        function clearAllSystemKeys() {
            if(confirm("Wipe custom user local storage matrix?")) {
                localStorage.removeItem('SHAYAN_BACKED_KEYS');
                initLocalStorageBackup();
                fetchState();
            }
        }

        document.getElementById('keyForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const isGlobal = document.getElementById('allToolsCheck').checked;
            let selectedTools = ['all'];
            
            if(!isGlobal) {
                selectedTools = Array.from(document.querySelectorAll('.tool-chk:checked')).map(c => c.value);
                if(selectedTools.length === 0) { return alert("Select at least one tool."); }
            }

            const payloadObject = {
                name: document.getElementById('clientName').value,
                key: document.getElementById('apiKey').value,
                limit: parseInt(document.getElementById('keyLimit').value),
                expire_date: document.getElementById('keyExpire').value,
                tools: selectedTools,
                used: localKeysCache[document.getElementById('apiKey').value]?.used || 0,
                status: localKeysCache[document.getElementById('apiKey').value]?.status || "Active"
            };

            const clientBackupPool = JSON.parse(localStorage.getItem('SHAYAN_BACKED_KEYS') || '{}');
            clientBackupPool[payloadObject.key] = payloadObject;
            localStorage.setItem('SHAYAN_BACKED_KEYS', JSON.stringify(clientBackupPool));

            await fetch('/api/admin/keys', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payloadObject)
            });

            resetFormState();
            fetchState();
        });

        function triggerEdit(keyId) {
            const k = localKeysCache[keyId];
            if(!k) return;
            document.getElementById('formTitle').innerHTML = `<i data-feather="edit" class="mr-2 w-4 h-4 text-blue-400"></i> Modify Active Token Profile`;
            document.getElementById('clientName').value = k.name;
            document.getElementById('apiKey').value = k.key;
            document.getElementById('apiKey').readOnly = true;
            document.getElementById('keyLimit').value = k.limit;
            document.getElementById('keyExpire').value = k.expire_date;
            
            const isAll = k.tools.includes('all');
            document.getElementById('allToolsCheck').checked = isAll;
            toggleAllTools({checked: isAll});
            document.querySelectorAll('.tool-chk').forEach(chk => { chk.checked = !isAll && k.tools.includes(chk.value); });
            document.getElementById('cancelEditBtn').classList.remove('hidden');
            document.getElementById('submitBtn').innerText = "SAVE MODIFICATIONS";
            feather.replace();
        }

        function resetFormState() {
            document.getElementById('formTitle').innerHTML = `<i data-feather="plus-circle" class="mr-2 w-4 h-4"></i> Provision Token Strategy`;
            document.getElementById('keyForm').reset();
            document.getElementById('apiKey').readOnly = false;
            document.getElementById('keyExpire').value = "2026-12-31T23:59";
            toggleAllTools({checked: true});
            document.getElementById('cancelEditBtn').classList.add('hidden');
            document.getElementById('submitBtn').innerText = "PROVISION ACCESS";
            feather.replace();
        }

        async function toggleSuspend(keyId, currentStatus) {
            const newStatus = currentStatus === 'Active' ? 'Suspended' : 'Active';
            const clientBackupPool = JSON.parse(localStorage.getItem('SHAYAN_BACKED_KEYS') || '{}');
            if(clientBackupPool[keyId]) clientBackupPool[keyId].status = newStatus;
            localStorage.setItem('SHAYAN_BACKED_KEYS', JSON.stringify(clientBackupPool));

            await fetch('/api/admin/keys/status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: keyId, status: newStatus })
            });
            fetchState();
        }

        async function dropKey(keyId) {
            if(confirm("Permanently wipe this routing token?")) {
                const clientBackupPool = JSON.parse(localStorage.getItem('SHAYAN_BACKED_KEYS') || '{}');
                delete clientBackupPool[keyId];
                localStorage.setItem('SHAYAN_BACKED_KEYS', JSON.stringify(clientBackupPool));

                await fetch(`/api/admin/keys/delete/${keyId}`, { method: 'DELETE' });
                fetchState();
            }
        }

        initLocalStorageBackup();
        initToolsCheckboxes();
        syncClientToServerFallback();
        setInterval(fetchLogs, 3000);
        setTimeout(() => { feather.replace(); }, 500);
    </script>
</body>
</html>
"""

def check_key_validity(api_key, tool_name):
    if api_key not in DB["keys"]:
        return False, "DEHYDRATED_KEY_DETECTED"
        
    key_data = DB["keys"][api_key]
    if key_data.get("status", "Active") == "Suspended":
        return False, "This API access footprint has been explicitly suspended."
    try:
        expire_dt = parser.parse(key_data["expire_date"])
        if datetime.now() > expire_dt:
            return False, f"API Key expired automatically on {key_data['expire_date']}."
    except Exception:
        return False, "System runtime token configuration parse exception."
    if int(key_data["used"]) >= int(key_data["limit"]):
        return False, f"Allocated quota threshold limit reached ({key_data['limit']})."
    allowed_tools = key_data.get("tools", [])
    if "all" not in allowed_tools and tool_name not in allowed_tools:
        return False, f"Access denied for router parameter: '{tool_name}'."
    return True, key_data

def sanitize_payload(data):
    banned = ["@ftgamer2", "@bornex", "Ultra", "ft-osint", "duckdns", "ft-rahun2m"]
    try:
        if isinstance(data, dict):
            cleaned_dict = {}
            for k, v in data.items():
                if any(b in str(k) for b in banned):
                    continue
                cleaned_dict[k] = sanitize_payload(v)
            return cleaned_dict
        elif isinstance(data, list):
            return [sanitize_payload(i) for i in data]
        elif isinstance(data, str):
            if "https://t.me/lynx_api" in data:
                data = data.replace("https://t.me/lynx_api", "https://t.me/shayan_explorer_channel")
            for b in banned:
                data = data.replace(b, "SHAYAN_EXPLORER")
            return data
    except Exception:
        return data
    return data

@app.route('/')
def dashboard():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/admin/keys', methods=['GET', 'POST'])
def handle_keys():
    if request.method == 'POST':
        data = request.json or {}
        key_id = data.get('key')
        if not key_id:
            return jsonify({"status": "error", "message": "Key code is mandatory"}), 400
        DB["keys"][key_id] = {
            "name": data.get('name', 'Client Target Profile'),
            "key": key_id,
            "expire_date": data.get('expire_date', '2026-12-31T23:59'),
            "limit": int(data.get('limit', 100)),
            "used": int(data.get('used', DB["keys"].get(key_id, {}).get("used", 0))),
            "status": data.get('status', DB["keys"].get(key_id, {}).get("status", "Active")),
            "tools": data.get('tools', ['all'])
        }
        return jsonify({"status": "success"})
    return jsonify(list(DB["keys"].values()))

@app.route('/api/admin/keys/sync', methods=['POST'])
def sync_all_keys():
    data = request.json or {}
    received_keys = data.get('keys', [])
    for k in received_keys:
        key_id = k.get('key')
        if key_id:
            if key_id not in DB["keys"]:
                DB["keys"][key_id] = k
            else:
                DB["keys"][key_id]["name"] = k.get("name", DB["keys"][key_id]["name"])
                DB["keys"][key_id]["limit"] = k.get("limit", DB["keys"][key_id]["limit"])
                DB["keys"][key_id]["expire_date"] = k.get("expire_date", DB["keys"][key_id]["expire_date"])
    return jsonify({"status": "success", "synced_count": len(received_keys)})

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

@app.route('/api/admin/logs', methods=['GET', 'POST'])
def handle_logs():
    if request.method == 'POST':
        DB["logs"] = []
        return jsonify({"status": "success"})
    return jsonify(DB["logs"])

@app.route('/api/<tool>', methods=['GET'])
def proxy_gateway(tool):
    if tool not in SUPPORTED_TOOLS:
        return jsonify({"status": "error", "developer": "SHAYAN_EXPLORER", "message": "Invalid Route."}), 404
    user_key = request.args.get('key')
    if not user_key:
        return jsonify({"status": "error", "developer": "SHAYAN_EXPLORER", "message": "Missing key parameters."}), 401
    
    is_valid, result = check_key_validity(user_key, tool)
    
    if not is_valid and result == "DEHYDRATED_KEY_DETECTED":
        return jsonify({
            "status": "error",
            "developer": "SHAYAN_EXPLORER",
            "message": "Gateway session synchronized. Please execute your network request again from the dashboard to auto-authenticate."
        }), 426

    if not is_valid:
        return jsonify({"status": "error", "developer": "SHAYAN_EXPLORER", "message": result}), 403

    key_data = result
    search_query = "Dynamic Data Request"
    
    for param in ['num', 'email', 'vehicle', 'username', 'uid', 'id', 'upi', 'ifsc', 'imei', 'ip', 'pin', 'info', 'pan']:
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

    if response.status_code == 200:
        key_data["used"] = int(key_data.get("used", 0)) + 1
        
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
        if "status" not in response_data:
            response_data["status"] = "SUCCESS"

    return jsonify(response_data), response.status_code

if __name__ == '__main__':
    app.run(debug=True, port=5000)
