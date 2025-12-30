from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api import routes, web

app = FastAPI(title="Migration Automater", version="1.0.0")

# Mount static files (for agent script)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include API routes
app.include_router(routes.router)

# Include Web UI routes
app.include_router(web.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
