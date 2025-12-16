import os
import yaml
import psutil
import time
import locale
import platform
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin requests

CONFIG_PATH = "config.yaml"
config = {}
current_users = 0

def detect_city_name():
    try:
        loc = locale.getdefaultlocale()[0]
        if loc:
            return loc.split("_")[0].upper()
    except:
        pass
    return "UNKNOWN"

def detect_region():
    system = platform.system()
    try:
        tz = time.tzname[0].lower()
    except:
        tz = "utc"

    if "europe" in tz or "cet" in tz or "eet" in tz or "bst" in tz:
        return "EU"
    if "africa" in tz:
        return "AFRICA"
    if "asia" in tz or "china" in tz or "tokyo" in tz:
        return "ASIA"
    if "australia" in tz or "nz" in tz:
        return "OCE"
    if "pacific" in tz:
        return "NA-WEST"
    if "mountain" in tz or "central" in tz:
        return "NA-CENTRAL"
    if "eastern" in tz or "est" in tz or "edt" in tz:
        return "NA-EAST"
    
    return "GLOBAL"

def benchmark_max_users():
    """
    Estimates how many concurrent users this specific PC can handle
    based on CPU speed and RAM.
    """
    try:
        cpu_cores = psutil.cpu_count(logical=True) or 2
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        
        start = time.time()
        count = 0
        while time.time() - start < 0.5:
            count += 1
        
        cpu_score = count / 100_000
        base_capacity = int(cpu_score * cpu_cores * 15) 
        ram_capacity = int(ram_gb * 50) 

        return max(10, min(base_capacity, ram_capacity))
    except:
        return 20 

def create_config():
    city = detect_city_name()
    region = detect_region()
    max_users = benchmark_max_users()

    new_config = {
        "server_name": f"{city}-NODE-{int(time.time()) % 1000}",
        "region": region,
        "max_users": max_users,
        "port": 5001 
    }

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(new_config, f)

    return new_config

def load_config():
    global config
    if not os.path.exists(CONFIG_PATH):
        print("Config not found — generating config.yaml...")
        config = create_config()
    else:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
            
        # FORCE CHECK: If port is missing or old default 5000, update it.
        if config.get("port") == 5000:
            print("WARNING: Config uses Port 5000. Changing to 5001 to avoid conflict.")
            config["port"] = 5001
            with open(CONFIG_PATH, "w") as f:
                yaml.dump(config, f)


@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({
        "name": config["server_name"],
        "region": config["region"],
        "max_users": config["max_users"],
        "current_users": current_users,
        "cpu_load": psutil.cpu_percent(interval=None),
        "ram_usage": psutil.virtual_memory().percent,
        "status": "online"
    })

@app.route('/connect', methods=['POST'])
def connect_user():
    global current_users
    if current_users < config["max_users"]:
        current_users += 1
        return jsonify({"status": "connected", "server": config["server_name"]}), 200
    return jsonify({"status": "full"}), 503

@app.route('/disconnect', methods=['POST'])
def disconnect_user():
    global current_users
    if current_users > 0:
        current_users -= 1
    return jsonify({"status": "disconnected"}), 200

if __name__ == "__main__":
    load_config()
    port = config.get("port", 5001)
    
    print(f"----------------------------------------")
    print(f" NODE AGENT RUNNING: {config['server_name']}")
    print(f" Region: {config['region']} | Capacity: {config['max_users']}")
    print(f" Listening on Port: {port}")
    print(f"----------------------------------------")
    
    app.run(host="0.0.0.0", port=port, threaded=True)