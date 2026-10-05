from flask import Flask, jsonify, abort
from flask_cors import CORS
import os
import json

app = Flask(__name__)
CORS(app)  # Maintains the Access-Control-Allow-Origin: * behavior from your original file

# Dynamically locate the data folder in the root directory relative to this api folder
DATA_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "../data"
)

@app.route('/api/projects', methods=['GET'])
def get_projects():
    try:
        # Check if the data directory exists
        if not os.path.exists(DATA_FOLDER):
            abort(404, description="Data folder not found")

        # Find all JSON files in the directory
        files = [
            f for f in os.listdir(DATA_FOLDER)
            if f.lower().endswith(".json")
        ]

        # Return error if folder is empty
        if not files:
            abort(404, description="No JSON files found in data folder")

        # Sort files to find the newest one by modification time
        files.sort(
            key=lambda f: os.path.getmtime(os.path.join(DATA_FOLDER, f)),
            reverse=True
        )

        # CORRECTED: Properly grab the first item (newest file string) from the list
        latest_file = files[0]
        latest_path = os.path.join(DATA_FOLDER, latest_file)

        # Safe read using UTF-8 encoding matching your original setup
        with open(latest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return jsonify(data)

    except Exception as e:
        # Return internal server errors with details
        abort(500, description=str(e))

# Vercel tracks this export variable 'app' to trigger execution
