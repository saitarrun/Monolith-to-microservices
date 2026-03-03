import asyncio
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import threading
import database
import models
from consumer import run_consumer

# Create tables
models.Base.metadata.create_all(bind=database.engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start consumer in a separate thread
    consumer_thread = threading.Thread(target=run_consumer, daemon=True)
    consumer_thread.start()
    yield

app = FastAPI(title="Orders Microservice", version="2.0.0", lifespan=lifespan)

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/v2/orders/")
def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    orders = db.query(models.Order).offset(skip).limit(limit).all()
    return orders

@app.get("/health")
def health_check():
    return {"status": "healthy"}
