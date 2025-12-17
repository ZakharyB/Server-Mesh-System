import requests
import time
import threading
import sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS 

app = Flask(__name__, static_folder='static') 

DB_FILE = "mesh_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (timestamp INTEGER, node_name TEXT, cpu_load REAL, ping REAL, users INTEGER)''')
    conn.commit()
    conn.close()

init_db()



NODES = [
    # MASTER NODE
    # Agent is on 5001, Website is on 80 (standard http)
    {
        "name": "Master-Node",
        "ip": "127.0.0.1", 
        "agent_port": 5001,   # Checks health here
        "web_port": 8000       # Sends users here
    },
    {
        "name": "JOLIETTE-NODE-001",
        "ip": "192.168.56.1", 
        "agent_port": 5001,   # Checks health here (JSON)
        "web_port": 8000      # Sends users here (FastAPI Website)
    },
    {
        "name": "JOLIETTE-NODE-002",
        "ip": "10.0.0.207", 
        "agent_port": 5002,   # Checks health here (JSON)
        "web_port": 8000      # Sends users here (FastAPI Website)
    },
        {
        "name": "NDP-NODE-002",
        "ip": "100.95.145.80", 
        "agent_port": 5003,   # Checks health here (JSON)
        "web_port": 8000      # Sends users here (FastAPI Website)
    }
]

SERVER_STATUS = {}
NODE_SETTINGS = {} 
PANIC_MODE = {"enabled": False, "url": "https://google.com"} 

def monitor_mesh():
    while True:
        timestamp = int(time.time())
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        for node in NODES:
            name = node['name']
            
            if name not in NODE_SETTINGS:
                NODE_SETTINGS[name] = {"maintenance": False, "weight": 1.0}

            try:
                start = time.time()
                r = requests.get(f"http://{node['ip']}:{node['agent_port']}/stats", timeout=2)
                latency = round((time.time() - start) * 1000, 2)
                
                if r.status_code == 200:
                    data = r.json()
                    
                    SERVER_STATUS[name] = {
                        "ip": node['ip'],
                        "web_port": node['web_port'],
                        "alive": True,
                        "ping": latency,
                        "users": data.get('current_users', 0),
                        "max": data.get('max_users', 100),
                        "load": data.get('cpu_load', 0),
                        "temp": data.get('temp'),
                        "watts": data.get('watts', 0),
                        "location": data.get('location', {}),
                        "maintenance": NODE_SETTINGS[name]['maintenance']
                    }

                    cursor.execute("INSERT INTO history VALUES (?, ?, ?, ?, ?)", 
                                   (timestamp, name, data.get('cpu_load',0), latency, data.get('current_users',0)))
                else:
                    raise Exception("Bad Status")
            except Exception as e:
                SERVER_STATUS[name] = {"alive": False, "ping": 9999, "error": str(e), "maintenance": False}

        conn.commit()
        conn.close()
        
        if timestamp % 3600 == 0:
             with sqlite3.connect(DB_FILE) as clean_conn:
                 cutoff = timestamp - 86400
                 clean_conn.execute("DELETE FROM history WHERE timestamp < ?", (cutoff,))

        time.sleep(3) 



@app.route('/dashboard')
def view_dashboard():
    return render_template('mesh_dashboard.html')

@app.route('/api/stats')
def api_stats():
    return jsonify({
        "nodes": SERVER_STATUS,
        "panic": PANIC_MODE
    })

@app.route('/api/history/<node_name>')
def api_history(node_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT timestamp, cpu_load, ping FROM history WHERE node_name=? ORDER BY timestamp DESC LIMIT 50", (node_name,))
    rows = c.fetchall()
    conn.close()
    
    data = [{"time": r[0], "load": r[1], "ping": r[2]} for r in rows][::-1]
    return jsonify(data)

@app.route('/api/control/maintenance', methods=['POST'])
def toggle_maintenance():
    data = request.json
    name = data.get('node')
    enabled = data.get('enabled')
    if name in NODE_SETTINGS:
        NODE_SETTINGS[name]['maintenance'] = enabled
        return jsonify({"success": True})
    return jsonify({"error": "Node not found"}), 404

@app.route('/api/control/panic', methods=['POST'])
def toggle_panic():
    data = request.json
    PANIC_MODE['enabled'] = data.get('enabled', False)
    if 'url' in data:
        PANIC_MODE['url'] = data['url']
    return jsonify({"success": True, "state": PANIC_MODE})

@app.route('/api/get-best')
def api_get_best():
    if PANIC_MODE['enabled']:
        return jsonify({"panic": True, "redirect_url": PANIC_MODE['url']})

    best = None
    lowest_score = float('inf')
    
    for name, s in SERVER_STATUS.items():
        if s.get('alive') and not s.get('maintenance') and s.get('users', 0) < s.get('max', 100):
            score = s['ping'] + (s.get('load', 0) * 2)
            if score < lowest_score:
                lowest_score = score
                best = s
                
    if best:
        return jsonify({"ip": best['ip'], "port": best['web_port']})
        
    return jsonify({"error": "No servers available"}), 503

if __name__ == "__main__":
    t = threading.Thread(target=monitor_mesh)
    t.daemon = True
    t.start()
    
    print("------------------------------------------------")
    print(" MESH CONTROLLER RUNNING ON PORT 5000")
    print("------------------------------------------------")
    
    app.run(host="0.0.0.0", port=5000)