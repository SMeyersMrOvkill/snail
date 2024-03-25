from flask import Flask, render_template, request, redirect, url_for, jsonify, request, Response
import json

import base64
import hashlib
import json
import time
import os
import queue
import zstandard as zstd

q = queue.Queue()

"""
Format:
{
    "status": "queue" | "progress" | "done"
    "prompt": "Some ducks..."
    "id": "abc123"
}
"""
models = []

WORKERS = []

def enqueue():
    data = request.json
    if not "prompt" in data:
        return jsonify({
            "status": "error",
            "reason": "missing 'prompt'"
        })
    prompt = data["prompt"]
    tm = time.time()
    hsh =  hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    md = {
        "status": "queue",
        "prompt": prompt,
        "id": f"{hsh}.{tm}"
    }
    models.append(md)
    q.put(json.dumps(md))
    return jsonify({
        "status": "ok"
    })
    
def dequeue():
    if not q.empty():
        pr = json.loads(q.get_nowait())
        return jsonify({
            "status": "ok",
            "prompt": pr["prompt"],
            "id": pr["id"]
        })
    return jsonify({
        "status": "empty"
    })
    
def complete():
    data = request.get_json(force=True)
    if not "files" in data:
        return jsonify({
            "status": "error",
            "action": "store"
        })
    if not "id" in data:
        return jsonify({
            "status": "error",
            "action": "store"
        })
    _id = data['id']
    for file in data['files']:
        pth = os.path.join(".", "requests", _id + ".json")
        if not os.path.exists(pth):
            os.makedirs(pth)
            os.rmdir(pth)
        f = open(pth, "w")
        f.write(json.dumps(file))
        
def worker():
    while True:
        if not q.empty():
            pr = json.loads(q.get_nowait())
            pr["status"] = "progress"
            for w in WORKERS:
                if w["status"] == "idle":
                    w["prompt"] = pr["prompt"]
                    w["id"] = pr["id"]
                    w["status"] = "queue"
                    break
            else:
                q.put(jsonify(pr))
        time.sleep(1)
        
app = Flask(__name__)

if __name__ == "__main__":
    app.add_url_rule("/enqueue", "enqueue", enqueue, methods=["POST"])
    app.add_url_rule("/dequeue", "dequeue", dequeue, methods=["GET"])
    app.add_url_rule("/complete", "complete", complete, methods=["POST"])
    app.add_url_rule("/", "index", lambda: """
<html>
<head>
    <title>Snail</title>
</head>
<body>
    <h1>Snail</h1>

</html>                     
""", methods=["GET"])
    
    app.static_folder = "public"
    
    app.run(port=7860, host="0.0.0.0")