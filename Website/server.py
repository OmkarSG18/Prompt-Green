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
def serve_website():
    return FileResponse(os.path.join(website_dir, "index.html"))

if __name__ == "__main__":
    print("Starting PromptGreen Production Web Application on http://localhost:8000 ...")
    uvicorn.run(api_app, host="127.0.0.1", port=8000)
