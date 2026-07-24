from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
import requests

app = Flask(__name__)
app.secret_key = "change_this_to_a_very_secure_random_secret_key"

# In-memory data store (For persistence in production, use SQLite/PostgreSQL)
# Keys format: { "KEY_NAME": { "expiry": "YYYY-MM-DDTHH:MM", "limit": int, "used": int } }
API_KEYS = {
    "explorer16": {
        "expiry": "2030-12-31T23:59",
        "limit": 10000,
        "used": 0,
    }
}

# Search history logs
SEARCH_HISTORY = []

# Admin credentials requested
ADMIN_USER = "verneX"
ADMIN_PASS = "verneX@16vx"

# Base upstream key configuration
UPSTREAM_KEY = "explorer16"

# Endpoints mapping dictionary
ENDPOINTS = {
    "adv": "https://ft-osint-api.duckdns.org/api/adv?key={key}&num={num}",
    "paytm": "https://ft-osint-api.duckdns.org/api/paytm?key={key}&num={num}",
    "imei": "https://ft-osint-api.duckdns.org/api/imei?key={key}&imei={imei}",
    "calltracer": "https://ft-osint-api.duckdns.org/api/calltracer?key={key}&num={num}",
    "upi": "https://ft-osint-api.duckdns.org/api/upi?key={key}&upi={upi}",
    "ifsc": "https://ft-osint-api.duckdns.org/api/ifsc?key={key}&ifsc={ifsc}",
    "pincode": "https://ft-osint-api.duckdns.org/api/pincode?key={key}&pin={pin}",
    "ip": "https://ft-osint-api.duckdns.org/api/ip?key={key}&ip={ip}",
    "challan": "https://ft-osint-api.duckdns.org/api/challan?key={key}&vehicle={vehicle}",
    "ff": "https://ft-osint-api.duckdns.org/api/ff?key={key}&uid={uid}",
    "bgmi": "https://ft-osint-api.duckdns.org/api/bgmi?key={key}&uid={uid}",
    "snap": "https://ft-osint-api.duckdns.org/api/snap?key={key}&username={username}",
    "number": "https://ft-osint-api.duckdns.org/api/number?key={key}&num={num}",
    "email": "https://ft-osint-api.duckdns.org/api/email?key={key}&email={email}",
    "vehicle": "https://ft-osint-api.duckdns.org/api/vehicle?key={key}&vehicle={vehicle}",
    "git": "https://ft-osint-api.duckdns.org/api/git?key={key}&username={username}",
    "insta": "https://ft-osint-api.duckdns.org/api/insta?key={key}&username={username}",
    "tg": "https://ft-osint-api.duckdns.org/api/tg?key={key}&info={info}",
    "tgidinfo": "https://ft-osint-api.duckdns.org/api/tgidinfo?key={key}&id={id}",
    "numleak": "https://ft-osint-api.duckdns.org/api/numleak?key={key}&num={num}",
}


def login_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if not session.get("logged_in"):
      return redirect(url_for("login"))
    return f(*args, **kwargs)

  return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
  error = None
  if request.method == "POST":
    if (
        request.form.get("username") == ADMIN_USER
        and request.form.get("password") == ADMIN_PASS
    ):
      session["logged_in"] = True
      return redirect(url_for("admin_dashboard"))
    else:
      error = "Invalid Credentials. Try verneX / verneX@16vx"
  return render_template("login.html", error=error)


@app.route("/logout")
def logout():
  session.clear()
  return redirect(url_for("login"))


@app.route("/")
def index():
  return render_template("index.html", endpoints=list(ENDPOINTS.keys()))


@app.route("/admin")
@login_required
def admin_dashboard():
  return render_template(
      "admin.html", keys=API_KEYS, history=SEARCH_HISTORY[::-1]
  )


@app.route("/admin/add_key", methods=["POST"])
@login_required
def add_key():
  key_name = request.form.get("key_name")
  expiry = request.form.get("expiry")
  limit = int(request.form.get("limit", 100))
  if key_name:
    API_KEYS[key_name] = {"expiry": expiry, "limit": limit, "used": 0}
  return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete_key/<key_name>")
@login_required
def delete_key(key_name):
  if key_name in API_KEYS:
    del API_KEYS[key_name]
  return redirect(url_for("admin_dashboard"))


# Universal API Gateway Endpoint
@app.route("/api/<tool_name>", methods=["GET"])
def api_gateway(tool_name):
  if tool_name not in ENDPOINTS:
    return (
        jsonify({"status": False, "error": "Invalid API tool specified."}),
        400,
    )

  client_key = request.args.get("key")
  if not client_key or client_key not in API_KEYS:
    return jsonify({"status": False, "error": "Unauthorized or Invalid Key."}), 403

  key_data = API_KEYS[client_key]

  # Check Expiry
  if key_data["expiry"]:
    try:
      expiry_dt = datetime.strptime(key_data["expiry"], "%Y-%m-%dT%H:%M")
      if datetime.now() > expiry_dt:
        return jsonify({"status": False, "error": "API Key has expired."}), 403
    except ValueError:
      pass

  # Check Limit
  if key_data["used"] >= key_data["limit"]:
    return jsonify({"status": False, "error": "API Key request quota exhausted."}), 403

  # Extract parameters dynamically
  param_values = {}
  for param in request.args:
    if param != "key":
      param_values[param] = request.args.get(param)

  # Increment usage tracking
  key_data["used"] += 1

  # Format upstream target URL
  target_url_template = ENDPOINTS[tool_name]
  try:
    # Safely inject upstream key and user args
    formatted_args = {"key": UPSTREAM_KEY, **param_values}
    upstream_url = target_url_template.format(**formatted_args)
  except KeyError as e:
    return (
        jsonify({
            "status": False,
            "error": f"Missing required parameter: {str(e)}",
        }),
        400,
    )

  # Log request in history
  SEARCH_HISTORY.append({
      "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      "key": client_key,
      "tool": tool_name,
      "params": str(param_values),
  })

  # Fetch response from upstream server securely
  try:
    response = requests.get(upstream_url, timeout=15)
    try:
      return jsonify(response.json())
    except ValueError:
      return jsonify({"status": True, "raw_response": response.text})
  except requests.exceptions.RequestException as e:
    return (
        jsonify({
            "status": False,
            "error": f"Upstream service connection error: {str(e)}",
        }),
        500,
    )


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000, debug=True)
