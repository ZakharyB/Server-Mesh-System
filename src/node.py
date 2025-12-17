import os
import yaml
import psutil
import time
import geocoder
import locale
import platform
from flask import Flask, jsonify, request
from flask_cors import CORS
import speedtest
import socket
import requests
from concurrent.futures import ThreadPoolExecutor
import threading

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin requests

CONFIG_PATH = "config.yaml"
config = {}
current_users = 0

def get_cpu_temp():
    """Attempts to read CPU temperature. Works best on Linux/macOS. 
    Windows often requires WMI or Admin rights."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps: return None
        for name, entries in temps.items():
            for entry in entries:
                if entry.current > 0: return entry.current
    except:
        return None 
    return None

def get_location():
    """Gets approximate location for the 3D Globe"""
    try:
        r = requests.get('http://ip-api.com/json/', timeout=3)
        data = r.json()
        return {
            "lat": data.get("lat", 0.0), 
            "lon": data.get("lon", 0.0),
            "city": data.get("city", "Unknown")
        }
    except:
        return {"lat": 0.0, "lon": 0.0, "city": "Unknown"}

def estimate_power_usage(cpu_percent):
    """Crude estimation: Idle (30W) + Max Load (100W)"""
    TDP = 105 # Watts
    IDLE = 30 # Watts
    watts = IDLE + ((cpu_percent / 100) * (TDP - IDLE))
    return round(watts, 1)

def detect_city_name():
    try:
        g = geocoder.ip('me')
        if g.ok:
            return g.city
    except:
        pass
    
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
    Real machine benchmark with:
    - Sustained CPU saturation (true load)
    - RAM-based hard limit
    - Upload-weighted network capacity
    - Write-heavy disk benchmark
    - Smart bottleneck modeling (CPU = soft cap)
    """

    metrics = {}

    try:

        cpu_cores = psutil.cpu_count(logical=True) or 2
        print("Benchmarking CPU (real sustained load)...")

        def cpu_load_test(_):
            end = time.time() + 1.5
            x = 1.000001
            ops = 0
            while time.time() < end:
                x *= 1.0000001
                ops += 1
            return ops

        with ThreadPoolExecutor(max_workers=cpu_cores) as executor:
            results = list(executor.map(cpu_load_test, range(cpu_cores)))

        total_ops = sum(results)
        ops_per_core = total_ops / cpu_cores

        cpu_capacity = max(10, int((ops_per_core / 250_000) * cpu_cores))
        metrics["cpu_capacity"] = cpu_capacity

        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        ram_capacity = max(10, int((ram_gb - 2) * 40)) 
        metrics["ram_capacity"] = ram_capacity


        print("Benchmarking network (upload-weighted)...")
        try:
            st = speedtest.Speedtest()
            st.get_best_server()

            download_mbps = st.download() / 1_000_000
            upload_mbps = st.upload() / 1_000_000

            download_kbps = download_mbps * 125
            upload_kbps = upload_mbps * 125

            user_bw_kbps = 3 
            net_capacity = int(
                ((upload_kbps * 5 + download_kbps) / 6) / user_bw_kbps * 0.8
            )

            metrics["network_capacity"] = max(10, net_capacity)
            metrics["download_mbps"] = round(download_mbps, 1)
            metrics["upload_mbps"] = round(upload_mbps, 1)

        except Exception as e:
            print("Network benchmark failed, using fallback:", e)
            metrics["network_capacity"] = 100


        print("Benchmarking disk I/O...")
        test_file = "io_bench.tmp"
        test_size_mb = 50

        start = time.time()
        with open(test_file, "wb") as f:
            f.write(b"\0" * (test_size_mb * 1024 * 1024))
        write_mbps = test_size_mb / max(0.01, time.time() - start)

        io_capacity = max(10, int((write_mbps * 1024) / 20))  
        metrics["io_capacity"] = io_capacity


        cpu = metrics["cpu_capacity"]
        ram = metrics["ram_capacity"]
        net = metrics["network_capacity"]
        io  = metrics["io_capacity"]

        io = min(io, ram * 3)
        net = min(net, ram * 2)

        hard_cap = min(ram, net)

        cpu_soft = cpu * 2.5

        weighted_capacity = int(
            1 / (
                (0.45 / cpu_soft) +
                (0.30 / ram) +
                (0.20 / net) +
                (0.05 / io)
            )
        )

        overall_capacity = max(10, min(weighted_capacity, hard_cap))
        metrics["overall_capacity"] = overall_capacity

        print("Benchmark results:", metrics)
        return overall_capacity

    except Exception as e:
        print("Benchmark error:", e)
        return 20

    """
    Real machine benchmark with:
    - TRUE sustained CPU load (100% per core)
    - RAM capacity estimation
    - Upload-weighted network benchmark
    - Disk I/O (write-heavy)
    Final result = lowest bottleneck
    """

    metrics = {}

    try:

        cpu_cores = psutil.cpu_count(logical=True) or 4
        print("Benchmarking CPU (real sustained load)...")

        def cpu_load_test(_):
            end = time.time() + 1.5  
            x = 1.000001
            ops = 0
            while time.time() < end:
                x *= 1.0000001
                ops += 1
            return ops

        with ThreadPoolExecutor(max_workers=cpu_cores) as executor:
            results = list(executor.map(cpu_load_test, range(cpu_cores)))

        total_ops = sum(results)
        ops_per_core = total_ops / cpu_cores


        cpu_capacity = max(10, int((ops_per_core / 250_000) * cpu_cores))
        metrics["cpu_capacity"] = cpu_capacity


        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        ram_capacity = max(10, int((ram_gb - 2) * 40)) 
        metrics["ram_capacity"] = ram_capacity


        print("Benchmarking network (upload-weighted)...")
        try:
            st = speedtest.Speedtest()
            st.get_best_server()

            download_mbps = st.download() / 1_000_000
            upload_mbps = st.upload() / 1_000_000

            download_kbps = download_mbps * 125
            upload_kbps = upload_mbps * 125

            user_bw_kbps = 3
            net_capacity = int(
                ((upload_kbps * 5 + download_kbps) / 6) / user_bw_kbps * 0.8
            )

            metrics["network_capacity"] = max(10, net_capacity)
            metrics["download_mbps"] = round(download_mbps, 1)
            metrics["upload_mbps"] = round(upload_mbps, 1)

        except Exception as e:
            print("Network benchmark failed, using fallback:", e)
            metrics["network_capacity"] = 100


        print("Benchmarking disk I/O...")
        test_file = "io_bench.tmp"
        test_size_mb = 50

        start = time.time()
        with open(test_file, "wb") as f:
            f.write(b"\0" * (test_size_mb * 1024 * 1024))
        write_mbps = test_size_mb / max(0.01, time.time() - start)

        io_capacity = max(10, int((write_mbps * 1024) / 5)) 
        metrics["io_capacity"] = io_capacity


        capacities = [
            metrics["cpu_capacity"],
            metrics["ram_capacity"],
            metrics["network_capacity"],
            metrics["io_capacity"],
        ]

        overall_capacity = max(10, min(capacities))
        metrics["overall_capacity"] = overall_capacity

        print("Benchmark results:", metrics)
        return overall_capacity

    except Exception as e:
        print("Benchmark error:", e)
        return 20

    """
    Enhanced PC benchmark prioritizing upload speed (5x more important than download).
    Assumes 1-5 KB/s per user (upload-dominant workload like file sharing, APIs).
    """
    metrics = {}
    
    try:
        cpu_cores = psutil.cpu_count(logical=True) or 2
        print("Benchmarking CPU...")
        
        def cpu_load_test():
            start = time.time()
            count = 0
            while time.time() - start < 1.0:
                count += 1
                _ = hash(str(count)) * 123.456
            return count

        def cpu_load_test(_):
            start = time.time()
            count = 0
            while time.time() - start < 1.0:
                count += 1
                _ = hash(str(count)) * 123.456
            return count

        
        with ThreadPoolExecutor(max_workers=cpu_cores) as executor:
            results = list(executor.map(cpu_load_test, range(cpu_cores)))
        
        total_cpu_score = sum(results) / 1_000_000
        cpu_capacity = int(total_cpu_score * cpu_cores * 10)
        metrics['cpu_capacity'] = cpu_capacity
        
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        ram_capacity = int((ram_gb - 2) * 40)  # ~25MB per user
        metrics['ram_capacity'] = ram_capacity
        
        print("Benchmarking network...")
        try:
            st = speedtest.Speedtest()
            st.get_best_server()
            
            download_mbps = st.download() / 1_000_000
            upload_mbps = st.upload() / 1_000_000
            
            download_kbps = download_mbps * 125
            upload_kbps = upload_mbps * 125
            
   
            user_bw_avg_kbps = 3 
            weighted_net_capacity = int((upload_kbps * 5 + download_kbps) / (user_bw_avg_kbps * 6) * 0.8)
            
            metrics['network_capacity'] = weighted_net_capacity
            metrics['download_mbps'] = round(download_mbps, 1)
            metrics['upload_mbps'] = round(upload_mbps, 1)
            metrics['upload_kbps'] = round(upload_kbps, 1)
        except:
            weighted_net_capacity = 100
            metrics['network_capacity'] = weighted_net_capacity
        
        print("Benchmarking disk...")
        test_file = 'io_bench.tmp'
        test_size_mb = 50
        
        start = time.time()
        with open(test_file, 'wb') as f:
            f.write(b'0' * (test_size_mb * 1024 * 1024))
        write_mbps = test_size_mb / (time.time() - start)
        
        io_capacity = int(write_mbps * 1024 / 5)  
        metrics['io_capacity'] = io_capacity
        
        capacities = [cpu_capacity, ram_capacity, weighted_net_capacity, io_capacity]
        overall_capacity = max(10, min(capacities))
        
        metrics['overall_capacity'] = overall_capacity
        metrics['capacities'] = capacities
        
        print(f"Upload-dominant metrics: {metrics}")
        return overall_capacity
        
    except Exception as e:
        print(f"Benchmark error: {e}")
        return 20

def create_config():
    city = detect_city_name()
    region = detect_region()
    max_users = benchmark_max_users()

    new_config = {
        "server_name": f"{city}-NODE-{int(time.time()) % 1000}",
        "region": region,
        "max_users": max_users,
        "port": 5001,
        "location": get_location() 
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
    cpu_load = psutil.cpu_percent(interval=None)
    
    return jsonify({
        "name": config["server_name"],
        "region": config["region"],
        "max_users": config["max_users"],
        "current_users": current_users,
        "cpu_load": cpu_load,
        "ram_usage": psutil.virtual_memory().percent,
        "temp": get_cpu_temp(),
        "watts": estimate_power_usage(cpu_load),
        "location": config.get("location"),
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