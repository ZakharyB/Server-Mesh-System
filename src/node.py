import yaml
import psutil
from flask import Flask, jsonify, request

app = Flask(__name__)
config = {}
current_users = 0

def load_config():
    global config
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

@app.route('/stats', methods=['GET'])
def get_stats():
    global current_users
    return jsonify({
        "name": config.get("server_name"),
        "region": config.get("region"),
        "max_users": config.get("max_users"),
        "current_users": current_users,
        "cpu_load": psutil.cpu_percent(),
        "ram_usage": psutil.virtual_memory().percent
    })

@app.route('/connect', methods=['POST'])
def connect_user():
    global current_users
    if current_users < config.get("max_users"):
        current_users += 1
        return jsonify({"status": "connected", "server": config.get("server_name")}), 200
    else:
        return jsonify({"status": "full"}), 503

@app.route('/disconnect', methods=['POST'])
def disconnect_user():
    global current_users
    if current_users > 0:
        current_users -= 1
    return jsonify({"status": "disconnected"}), 200

if __name__ == "__main__":
    load_config()
    app.run(host="0.0.0.0", port=config.get("port", 5000))