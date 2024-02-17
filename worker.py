import base64
import os
import subprocess
import time
import json
from diffusers import AutoPipelineForText2Image
import zstandard as zstd
import torch
import pickle
import hashlib
import requests

pipes = {}
pipes["opendalle"] = AutoPipelineForText2Image.from_pretrained('dataautogpt3/OpenDalleV1.1', torch_dtype=torch.float16).to("cuda")

def mkbpk(files: list, id: str):
    ls = {
        "_id": id,
        "files": []
    }
    for fl in files:
        with open(fl, "rb") as f:
            rd = f.read()
            print(f"Compressing\n{fl}...")
            ls["files"].append({
                "path": fl,
                "data": base64.b64encode(zstd.compress(rd)).decode("utf-8")
            })
    return ls

def opendalle(prompt: str):
    print("Generating OpenDalle Image...")
    img = pipes["opendalle"](prompt).images[0]
    pck = pickle.dumps(img)
    hsh = hashlib.sha256(pck).hexdigest()
    tm = time.time()
    pth = f"outputs/opendalle/{hsh}.{tm}.png"
    img.save(pth, "PNG")
    return pth

global workers
workers = []

def loadworkers():
    workers = []
    setups = []
    fnl = []
    for wrk in os.listdir("workers"):
        if wrk.endswith(".py"):
            proc = subprocess.Popen(executable="/usr/bin/env", args=["python", wrk, "--prompt", "dry_run"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
            rc = proc.wait()
            print(f"Popen returned {rc}")
            if not rc or rc == 0:
                fnl.append({
                    "name": wrk,
                    "setup": True
                })
                continue
            stdout, stderr = proc.communicate()
            fnl.append({
                "name": wrk,
                "setup": f"""--- Output ---
        {stdout}
        --- Error ---
        {stderr}
        """
            })
            return fnl

loadworkers()

while True:
    res = requests.get("http://localhost:7860/dequeue")
    if res.status_code != 200:
        print("Error. Sleeping 10s...")
        time.sleep(10)
        continue
    jsn = res.json()
    if jsn["status"] == "empty":
        print("No work. Sleeping 10s...")
        time.sleep(10)
        continue
    prompt = jsn["prompt"]
    status = jsn["status"]
    id = jsn["id"]
    if status.lower() == "ok":
        print(f"Acquired prompt '{prompt}'. Generating...")
        imgs = []
        imgs.append(opendalle(prompt))
        print("Generated. Uploading...")
        r = requests.post("http://localhost:7860/complete", json=mkbpk(imgs, id))
    else:
        print("No work. Sleeping 10s...")
        time.sleep(10)