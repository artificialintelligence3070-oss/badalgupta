'use client';
import { useState } from 'react';

export default function Dashboard() {
  const [keys, setKeys] = useState([
    { name: "Default Admin", key: "my-custom-super-key-123", expiryDate: "2027-12-31", dailyLimit: 100, usedToday: 0 }
  ]);
  
  // Form States
  const [name, setName] = useState('');
  const [customKey, setCustomKey] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [dailyLimit, setDailyLimit] = useState('');
  
  // API Tester States
  const [testKey, setTestKey] = useState('my-custom-super-key-123');
  const [testNum, setTestNum] = useState('9876543210');
  const [apiResponse, setApiResponse] = useState(null);

  const handleCreateKey = async (e) => {
    e.preventDefault();
    const payload = { name, key: customKey, expiryDate, dailyLimit };

    const res = await fetch('/api/proxy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success) {
      setKeys(data.keys);
      setName(''); setCustomKey(''); setExpiryDate(''); setDailyLimit('');
    }
  };

  const handleTestApi = async () => {
    setApiResponse("Fetching data from your proxy...");
    try {
      const res = await fetch(`/api/proxy?key=${testKey}&num=${testNum}`);
      const data = await res.json();
      setApiResponse(JSON.stringify(data, null, 2));
    } catch (err) {
      setApiResponse("Error executing request.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8 font-sans bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/40 via-slate-950 to-black">
      
      {/* Header Banner */}
      <header className="max-w-7xl mx-auto mb-12 text-center md:text-left">
        <h1 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-cyan-400 to-indigo-500 filter drop-shadow-sm">
          NEXUS 3D OSINT PROXY CORE
        </h1>
        <p className="text-slate-400 mt-2">Scale, restrict, and monitor upstream lookups flawlessly.</p>
      </header>

      <main className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: 3D Control Configuration Box */}
        <div className="lg:col-span-1 bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-2xl transform hover:-translate-y-1 transition-all duration-300 shadow-[5px_5px_0px_0px_rgba(59,130,246,0.3)]">
          <h2 className="text-xl font-bold mb-4 flex items-center text-blue-400">
            <span className="mr-2">🔑</span> Generate Secure Key
          </h2>
          
          <form onSubmit={handleCreateKey} className="space-y-4">
            <div>
              <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1">Custom Name Identifier</label>
              <input required type="text" value={name} onChange={e => setName(e.target.value)} placeholder="e.g., Enterprise Client" className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors" />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1">Custom Token Key string</label>
              <input required type="text" value={customKey} onChange={e => setCustomKey(e.target.value)} placeholder="e.g., custom-premium-token" className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors" />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1">Expiration Date</label>
              <input required type="date" value={expiryDate} onChange={e => setExpiryDate(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors" />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1">Max Daily Request Capacity</label>
              <input required type="number" value={dailyLimit} onChange={e => setDailyLimit(e.target.value)} placeholder="e.g., 500" className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors" />
            </div>
            
            <button type="submit" className="w-full mt-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg py-2.5 font-medium shadow-[0_4px_12px_rgba(59,130,246,0.3)] transform active:scale-95 transition-all text-sm">
              Deploy Key Rule
            </button>
          </form>
        </div>

        {/* Right Column: Live Data Grid & Interactive Playground */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* Active Custom Keys Grid */}
          <div className="bg-slate-900/40 border border-slate-800/80 p-6 rounded-2xl shadow-xl">
            <h2 className="text-xl font-bold mb-4 text-cyan-400">Active Gateways</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {keys.map((k, i) => (
                <div key={i} className="bg-gradient-to-br from-slate-900 to-slate-950 p-4 border border-slate-800 rounded-xl relative overflow-hidden group shadow-[0_10px_30px_rgba(0,0,0,0.5)]">
                  <div className="absolute top-0 right-0 h-16 w-16 bg-blue-500/10 rounded-bl-full filter blur-md group-hover:bg-blue-500/20 transition-all"></div>
                  <h3 className="font-bold text-slate-200 text-lg">{k.name}</h3>
                  <p className="text-xs font-mono text-blue-400 mt-1 truncate bg-slate-950 p-1.5 rounded border border-slate-900">{k.key}</p>
                  
                  <div className="grid grid-cols-2 gap-2 mt-4 pt-2 border-t border-slate-800/60 text-xs text-slate-400">
                    <div>📅 Expires: <span className="text-slate-200 font-semibold">{k.expiryDate}</span></div>
                    <div>📊 Limit: <span className="text-slate-200 font-semibold">{k.usedToday} / {k.dailyLimit}</span></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 3D Sandbox Terminal Environment */}
          <div className="bg-black/80 border border-slate-800 rounded-2xl overflow-hidden shadow-[0_30px_60px_rgba(0,0,0,0.8)]">
            <div className="bg-slate-900/90 px-4 py-3 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="w-3 h-3 rounded-full bg-red-500 inline-block"></span>
                <span className="w-3 h-3 rounded-full bg-yellow-500 inline-block"></span>
                <span className="w-3 h-3 rounded-full bg-green-500 inline-block"></span>
                <span className="text-xs font-mono text-slate-400 ml-2">Sandbox Endpoint Studio</span>
              </div>
              <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded font-mono">GET</span>
            </div>

            <div className="p-6 space-y-4">
              <div className="flex flex-col md:flex-row gap-3">
                <input type="text" value={testKey} onChange={e => setTestKey(e.target.value)} placeholder="Auth Key" className="flex-1 bg-slate-950 border border-slate-800 text-slate-300 font-mono text-xs rounded-lg p-2 focus:outline-none focus:border-cyan-500" />
                <input type="text" value={testNum} onChange={e => setTestNum(e.target.value)} placeholder="Phone Target Number" className="flex-1 bg-slate-950 border border-slate-800 text-slate-300 font-mono text-xs rounded-lg p-2 focus:outline-none focus:border-cyan-500" />
                <button onClick={handleTestApi} className="bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs px-5 py-2 rounded-lg transition-transform active:scale-95 shadow-[0_0_15px_rgba(6,182,212,0.4)]">
                  Trigger Request
                </button>
              </div>

              {/* Console Output Block */}
              <div className="bg-slate-950 rounded-xl p-4 border border-slate-900 h-48 overflow-y-auto font-mono text-xs text-green-400 shadow-inner">
                {apiResponse ? (
                  <pre className="whitespace-pre-wrap">{apiResponse}</pre>
                ) : (
                  <span className="text-slate-600">// Waiting for deployment queries... Execute request above to view runtime tracking updates.</span>
                )}
              </div>
            </div>

          </div>

        </div>
      </main>
    </div>
  );
}
