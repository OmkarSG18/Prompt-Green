import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Ensure root path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from promptgreen.api.server import app as api_app

# Mount web UI files
website_dir = os.path.dirname(__file__)

@api_app.get("/")
@api_app.get("/app")
@api_app.get("/website")
@api_app.get("/studio")
@api_app.get("/about")
@api_app.get("/v1")
@api_app.get("/v2")
def serve_website():
    return FileResponse(os.path.join(website_dir, "index.html"))

@api_app.get("/evaluation")
@api_app.get("/evolution")
def serve_evaluation():
    eval_path = os.path.join(website_dir, "evaluation.html")
    if os.path.exists(eval_path):
        return FileResponse(eval_path)
    return FileResponse(os.path.join(website_dir, "index.html"))

def _open_browser_when_ready():
    if os.environ.get("PROMPTGREEN_NO_BROWSER", "").strip() == "1":
        return
    import threading, time, urllib.request, webbrowser
    def _poll_and_open():
        for _ in range(60):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/api", timeout=1) as resp:
                    if resp.status == 200:
                        print("\n[READY] PromptGreen V2 is online and operational at http://127.0.0.1:8000")
                        webbrowser.open("http://127.0.0.1:8000")
                        return
            except Exception:
                pass
    t = threading.Thread(target=_poll_and_open, daemon=True)
    t.start()

if __name__ == "__main__":
    print("Starting PromptGreen Production Web Application on http://127.0.0.1:8000 ...")
    _open_browser_when_ready()
    uvicorn.run(api_app, host="127.0.0.1", port=8000)
