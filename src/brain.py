import requests
import time
import threading
from flask import Flask, jsonify, render_template
from flask_cors import CORS 

app = Flask(__name__)
CORS(app) 

NODES = [
    {"ip": "127.0.0.1", "port": 8080, "name": "Master-Node-Backup"}, 
    {"ip": "192.168.56.1", "port": 5001, "name": "Worker-PC-1"},
    {"ip": "192.168.1.16", "port": 80, "name": "Worker-PC-2"}
]

SERVER_STATUS = {}

def monitor_mesh():
    while True:
        for node in NODES:
            try:
                start = time.time()
                # url = f"http://{node['ip']}:{node['port']}/status.php"
                url = f"http://{node['ip']}:{node['port']}/stats"  

                r = requests.get(url, timeout=2)
                latency = round((time.time() - start) * 1000, 2)
                
                if r.status_code == 200:
                    data = r.json()
                    SERVER_STATUS[node['name']] = {
                        "ip": node['ip'],
                        "alive": True,
                        "ping": latency,
                        "users": data.get('current_users', 0),
                        "max": data.get('max_users', 100),
                        "load": data.get('cpu_load', 0)
                    }
                else:
                    raise Exception("Bad Status")
            except Exception as e:
                SERVER_STATUS[node['name']] = {
                    "ip": node['ip'], 
                    "alive": False, 
                    "ping": 9999,
                    "error": str(e)
                }
        time.sleep(3)



@app.route('/dashboard')
def view_dashboard():
    return render_template('mesh_dashboard.html')

@app.route('/api/stats')
def api_stats():
    return jsonify(SERVER_STATUS)

@app.route('/api/get-best')
def api_get_best():
    best = None
    lowest_score = float('inf')
    
    for name, s in SERVER_STATUS.items():
        if s.get('alive') and s.get('users', 0) < s.get('max', 100):
            score = s['ping'] + (s.get('load', 0) * 2)
            if score < lowest_score:
                lowest_score = score
                best = s
                
    if best:
        return jsonify({"ip": best['ip'], "port": 80}) 
    return jsonify({"error": "No servers available"}), 503

if __name__ == "__main__":
    t = threading.Thread(target=monitor_mesh)
    t.daemon = True
    t.start()
    
    print("------------------------------------------------")
    print(" MESH CONTROLLER RUNNING ON PORT 5000")
    print(" Access Dashboard at: http://localhost:5000/dashboard")
    print("------------------------------------------------")
    
    app.run(host="0.0.0.0", port=5000)