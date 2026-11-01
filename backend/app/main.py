# Trip Planner Agent — backend entry point
from fastapi import FastAPI

app = FastAPI(title="Trip Planner Agent")


@app.get("/health")
def health():
    return {"status": "ok"}
