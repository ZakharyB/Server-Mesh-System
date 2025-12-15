import time
import requests
from ping3 import ping
from flask import Flask, jsonify, render_template, request, redirect

app = Flask(__name__)

MESH_NODES = [
    "http://127.0.0.1:5001",
    "http://192.168.1.15:5002" 
]

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/mesh-status')
def mesh_status():
    results = []
    for node_url in MESH_NODES:
        try:
            ip = node_url.replace("http://", "").split(":")[0]
            latency = ping(ip, timeout=0.5)
            if latency is None:
                latency_ms = 9999
            else:
                latency_ms = round(latency * 1000, 2)

            resp = requests.get(f"{node_url}/stats", timeout=1)
            if resp.status_code == 200:
                data = resp.json()
                data['url'] = node_url
                data['ping'] = latency_ms
                data['status'] = 'Online'
                results.append(data)
        except:
            results.append({
                'url': node_url,
                'name': 'Unknown',
                'status': 'Offline',
                'ping': -1,
                'current_users': 0,
                'max_users': 0
            })
    return jsonify(results)

@app.route('/get-best-server')
def get_best_server():
    best_node = None
    lowest_metric = float('inf')

    for node_url in MESH_NODES:
        try:
            ip = node_url.replace("http://", "").split(":")[0]
            latency = ping(ip, timeout=0.5) or 10
            
            resp = requests.get(f"{node_url}/stats", timeout=0.5)
            if resp.status_code == 200:
                data = resp.json()
                if data['current_users'] < data['max_users']:
                    metric = latency 
                    if metric < lowest_metric:
                        lowest_metric = metric
                        best_node = node_url
        except:
            continue
    
    if best_node:
        return jsonify({"redirect_to": best_node})
    else:
        return jsonify({"error": "No available servers"}), 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)