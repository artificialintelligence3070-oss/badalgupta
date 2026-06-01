from flask import Flask, request, jsonify
import requests
import json
from datetime import datetime

app = Flask(__name__)

UPSTREAM_API = "https://ft-osint-api.duckdns.org/api/number"
UPSTREAM_KEY = "ft-rahun2m"


def validate_key(user_key):
    try:
        with open("keys.json", "r") as f:
            keys = json.load(f)

        if user_key not in keys:
            return False

        expiry = datetime.strptime(keys[user_key], "%Y-%m-%d")

        return expiry >= datetime.now()

    except:
        return False


@app.route("/api/number")
def number_lookup():

    api_key = request.args.get("key")
    number = request.args.get("num")

    if not api_key:
        return jsonify({"status": False, "message": "API key required"}), 401

    if not validate_key(api_key):
        return jsonify({"status": False, "message": "Invalid or expired API key"}), 403

    response = requests.get(
        UPSTREAM_API,
        params={
            "key": UPSTREAM_KEY,
            "num": number
        },
        timeout=30
    )

    data = response.json()

    # Remove branding fields
    data.pop("by", None)
    data.pop("channel", None)

    # Add your branding
    data["by"] = "VERNEX"

    return jsonify(data)


if __name__ == "__main__":
    app.run()
