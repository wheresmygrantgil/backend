from fastapi import FastAPI
from .database import Base, engine
from .routes import router
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from fastapi.middleware.cors import CORSMiddleware

# Initialize DB
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Grant Votes API")
app.state.limiter = router.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS (update with your GitHub Pages domain)
origins = ["https://wheresmygrants.github.io", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
