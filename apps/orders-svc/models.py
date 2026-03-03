from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base
import datetime

class Order(Base):
    __tablename__ = "orders_microservice"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    product_id = Column(String, index=True)
    amount = Column(Float)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # For backfill/verification
    original_id = Column(Integer, unique=True, index=True) 
