from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

API_KEY = "ft-rahun2m"

@app.route("/")
def home():
    return jsonify({
        "owner": "VERNEX",
        "status": "online"
    })

@app.route("/api/number")
def number():

    num = request.args.get("num")

    if not num:
        return jsonify({
            "status": False,
            "message": "num parameter required"
        })

    url = f"https://ft-osint-api.duckdns.org/api/number?key={API_KEY}&num={num}"

    try:
        r = requests.get(url, timeout=20)
        data = r.json()

        # Remove branding
        data.pop("channel", None)

        # Change owner
        data["by"] = "VERNEX"

        return jsonify(data)

    except Exception as e:
        return jsonify({
            "status": False,
            "error": str(e)
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
