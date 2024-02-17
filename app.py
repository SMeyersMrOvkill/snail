from flask import Flask, render_template, request, redirect, url_for, jsonify, Request, Response
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

def enqueue(prompt: str):
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
    
def complete(data):
    jsn = json.loads(data)
    for i in range(len(models)):
        if models[i]["id"] == jsn["_id"]:
            models[i]["status"] = "done"
            for fl in jsn["files"]:
                rd = zstd.decompress(base64.b64decode(fl["data"]))
                os.makedirs(f"files/{fl['path']}", exist_ok=True)
                os.rmdir(f"files/{fl['path']}")
                with open(f"files/{fl['path']}", "wb") as f:
                    f.write(rd)
                    f.flush()
                    f.close()
            break
    return jsonify({"status": "ok"})
        
def worker():
    while True:
        if not q.empty():
            pr = json.loads(q.get_nowait())
            pr["status"] = "progress"
            for w in WORKERS:
                if w["status"] == "idle":
                    w["prompt"] = pr["prompt"]
                    w["id"] = pr["id"]
                    break
            else:
                q.put(jsonify(pr))
        time.sleep(1)
        
app = Flask(__name__)

if __name__ == "__main__":
    app.add_url_rule("/enqueue/<prompt>", "enqueue", enqueue, methods=["POST"])
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