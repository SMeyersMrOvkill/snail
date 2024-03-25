import base64
import os
import subprocess
import time
import json
from transformers import AutoTokenizer, AutoModelForCausalLM
import zstandard as zstd
import torch
import pickle
import hashlib
import requests

pipes = {}
#pipes["opendalle"] = AutoPipelineForText2Image.from_pretrained('dataautogpt3/OpenDalleV1.1', torch_dtype=torch.float16).to("cuda")

def __call_gemma_sm(prompt: str):
    pass

pipes["gemma-sm"] = {
    "model": AutoModelForCausalLM.from_pretrained("google/gemma-2b-it"),
    "tokenizer": AutoTokenizer.from_pretrained("google/gemma-2b-it"),
    "call": __call_gemma_sm
}

def mkbpk(files: list, _id: str):
    ls = {
        "id": _id,
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

while True:
    res = requests.get("http://127.0.0.1:7860/dequeue")
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
    _id = jsn["id"]
    if status.lower() == "ok":
        print(f"Acquired prompt '{prompt}'. Generating...")
        pk = mkbpk([pipes['gemma-sm']["call"](prompt)], _id)
        hdr = {
            "Content-Type": "application/json"
        }
        res = requests.post("http://127.0.0.1:7860/complete", json=pk, headers=hdr)
        print(res.json())
    else:
        print("No work. Sleeping 10s...")
        time.sleep(10)