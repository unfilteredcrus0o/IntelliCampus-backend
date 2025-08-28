from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.auth import router as auth_router
from api.health import router as health_router
from api.roadmap import router as roadmap_router
from api.assignments import router as assignments_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to IntelliCampus API"}

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(roadmap_router)
app.include_router(assignments_router)