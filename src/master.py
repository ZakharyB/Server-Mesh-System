import requests
import time
import threading
from flask import Flask, request, Response, render_template_string, jsonify

app = Flask(__name__)

# CONFIGURATION
NODES = [
    {"ip": "192.168.1.11", "port": 80, "name": "XAMPP-Node-1", "region": "US"},
    {"ip": "192.168.1.12", "port": 80, "name": "XAMPP-Node-2", "region": "EU"},
]

NODE_STATS = {}

def check_health():
    while True:
        for node in NODES:
            url = f"http://{node['ip']}:{node['port']}/status.php"
            try:
                start = time.time()
                resp = requests.get(url, timeout=1)
                latency = (time.time() - start) * 1000
                
                if resp.status_code == 200:
                    data = resp.json()
                    NODE_STATS[node['name']] = {
                        "ip": node['ip'],
                        "alive": True,
                        "ping": round(latency, 2),
                        "load": data.get('cpu_load', 0),
                        "users": data.get('current_users', 0),
                        "max": data.get('max_users', 100)
                    }
                else:
                    raise Exception("Status 500")
            except:
                NODE_STATS[node['name']] = {
                    "ip": node['ip'],
                    "alive": False,
                    "ping": 9999,
                    "load": 0,
                    "users": 0,
                    "max": 0
                }
        time.sleep(5)

def get_best_node():
    best = None
    min_score = float('inf') 
    
    for name, stats in NODE_STATS.items():
        if not stats['alive']: continue
        if stats['users'] >= stats['max']: continue
        
        # Score based on Ping + Load (Lower is better)
        score = stats['ping'] + (stats['load'] * 2)
        
        if score < min_score:
            min_score = score
            best = stats
            
    return best

@app.route('/admin/dashboard')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mesh Load Balancer</title>
        <style>
            body { background: #111; color: white; font-family: sans-serif; padding: 20px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; }
            .card { background: #222; padding: 20px; border-radius: 8px; border-left: 5px solid #555; }
            .online { border-color: #0f0; }
            .offline { border-color: #f00; }
            h2 { margin-top: 0; }
        </style>
        <script>
            setInterval(() => window.location.reload(), 3000);
        </script>
    </head>
    <body>
        <h1>Cluster Status</h1>
        <div class="grid">
            {% for name, node in nodes.items() %}
            <div class="card {{ 'online' if node.alive else 'offline' }}">
                <h2>{{ name }}</h2>
                <p>IP: {{ node.ip }}</p>
                <p>Status: {{ 'ONLINE' if node.alive else 'OFFLINE' }}</p>
                <p>Ping: {{ node.ping }}ms</p>
                <p>Load: {{ node.users }} / {{ node.max }} Users</p>
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html, nodes=NODE_STATS)

# REVERSE PROXY LOGIC
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy(path):
    target = get_best_node()
    
    if not target:
        return "No servers available", 503

    target_url = f"http://{target['ip']}/{path}"
    
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers={key: value for (key, value) in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            params=request.args
        )

        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

if __name__ == "__main__":
    t = threading.Thread(target=check_health)
    t.daemon = True
    t.start()
    
    # Run on Port 80 for Cloudflare
  #  app.run(host="0.0.0.0", port=80, threaded=True) 
    app.run(host="0.0.0.0", port=80, threaded=True)