import { NextResponse } from 'next/server';

// Mock In-Memory Database for Vercel Serverless environment 
// (For permanent storage, link this to Vercel KV / Redis)
if (!global.apiKeysConfig) {
  global.apiKeysConfig = [
    {
      name: "Default Admin",
      key: "my-custom-super-key-123",
      expiryDate: "2027-12-31",
      dailyLimit: 100,
      usedToday: 0,
    }
  ];
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const userKey = searchParams.get('key');
  const num = searchParams.get('num');

  if (!userKey || !num) {
    return NextResponse.json({ error: "Missing required query parameters: 'key' and 'num'" }, { status: 400 });
  }

  // Find your custom API key configuration
  const keyConfig = global.apiKeysConfig.find(k => k.key === userKey);

  if (!keyConfig) {
    return NextResponse.json({ error: "Unauthorized: Invalid custom API key" }, { status: 401 });
  }

  // 1. Check Expiry Date
  const today = new Date();
  const expiry = new Date(keyConfig.expiryDate);
  if (today > expiry) {
    return NextResponse.json({ error: "Forbidden: This API key has expired" }, { status: 403 });
  }

  // 2. Check Daily Limit
  if (keyConfig.usedToday >= keyConfig.dailyLimit) {
    return NextResponse.json({ error: "Too Many Requests: Daily usage limit reached" }, { status: 429 });
  }

  try {
    // Increment usage counter
    keyConfig.usedToday += 1;

    // Forward the request to the target OSINT API
    const targetUrl = `https://ft-osint-api.duckdns.org/api/number?key=ft-rahun2m&num=${num}`;
    const response = await fetch(targetUrl);
    const data = await response.json();

    // Return the response along with meta statistics
    return NextResponse.json({
      success: true,
      clientMeta: {
        keyName: keyConfig.name,
        remainingRequests: keyConfig.dailyLimit - keyConfig.usedToday,
        expiry: keyConfig.expiryDate
      },
      data: data
    });

  } catch (error) {
    return NextResponse.json({ error: "Failed to fetch from upstream OSINT API" }, { status: 500 });
  }
}

// Separate POST endpoint used by the Dashboard UI to add/modify custom keys
export async function POST(request) {
  try {
    const body = await request.json();
    const { name, key, expiryDate, dailyLimit } = body;

    if (!name || !key || !expiryDate || !dailyLimit) {
      return NextResponse.json({ error: "Missing configuration fields" }, { status: 400 });
    }

    // Upsert key configuration
    const existingIndex = global.apiKeysConfig.findIndex(k => k.key === key);
    const newConfig = { name, key, expiryDate, dailyLimit: parseInt(dailyLimit), usedToday: 0 };

    if (existingIndex > -1) {
      global.apiKeysConfig[existingIndex] = newConfig;
    } else {
      global.apiKeysConfig.push(newConfig);
    }

    return NextResponse.json({ success: true, keys: global.apiKeysConfig });
  } catch (err) {
    return NextResponse.json({ error: "Invalid request payload" }, { status: 500 });
  }
}
