"""
Dispatcher Backend API
Handles dispatcher login, shipment management, driver assignment, and status updates
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from backend.shared.database import get_db, engine, Base
from backend.shared.models import User, Shipment, Driver, UserRole, ShipmentStatus
from backend.shared.utils import verify_password, create_access_token
from backend.shared.config import settings

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Logistics - Dispatcher API",
    description="Dispatcher login, shipment assignment, and status updates",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ Pydantic Models ------------------

class DispatcherLogin(BaseModel):
    email: EmailStr
    password: str

class ShipmentAssign(BaseModel):
    driver_id: int

class ShipmentStatusUpdate(BaseModel):
    status: ShipmentStatus

# ------------------ Routes ------------------

@app.get("/")
async def root():
    return {"message": "Dispatcher Backend API", "status": "running"}

# ------------------ DISPATCHER LOGIN ------------------

@app.post("/api/dispatcher/login")
async def dispatcher_login(credentials: DispatcherLogin, db: Session = Depends(get_db)):
    """Dispatcher login"""
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.role != UserRole.DISPATCHER:
        raise HTTPException(status_code=403, detail="Dispatcher access only")

    token = create_access_token(data={"sub": user.email, "role": user.role.value})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
        }
    }

# ------------------ SHIPMENTS ------------------

@app.get("/api/dispatcher/shipments")
async def get_all_shipments(db: Session = Depends(get_db)):
    """Get all shipments"""
    shipments = db.query(Shipment).all()

    return [
        {
            "id": s.id,
            "shipment_number": s.shipment_number,
            "pickup_location": s.pickup_location,
            "delivery_location": s.delivery_location,
            "cargo_type": s.cargo_type,
            "weight": s.weight,
            "dimensions": s.dimensions,
            "status": s.status.value,
            "customer_id": s.customer_id,
            "driver_id": s.driver_id,
            "created_at": s.created_at
        }
        for s in shipments
    ]

@app.get("/api/dispatcher/shipments/{shipment_id}")
async def get_shipment_detail(shipment_id: int, db: Session = Depends(get_db)):
    """Get single shipment details"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    return {
        "id": shipment.id,
        "shipment_number": shipment.shipment_number,
        "pickup_location": shipment.pickup_location,
        "delivery_location": shipment.delivery_location,
        "cargo_type": shipment.cargo_type,
        "weight": shipment.weight,
        "dimensions": shipment.dimensions,
        "status": shipment.status.value,
        "customer_id": shipment.customer_id,
        "driver_id": shipment.driver_id,
        "created_at": shipment.created_at
    }

# ------------------ ASSIGN DRIVER ------------------

@app.post("/api/dispatcher/shipments/{shipment_id}/assign")
async def assign_driver(
    shipment_id: int,
    assignment: ShipmentAssign,
    db: Session = Depends(get_db)
):
    """Assign driver to shipment"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    driver = db.query(Driver).filter(Driver.id == assignment.driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    shipment.driver_id = driver.id
    shipment.status = ShipmentStatus.ASSIGNED
    db.commit()
    db.refresh(shipment)

    return {
        "message": "Driver assigned successfully",
        "shipment_number": shipment.shipment_number,
        "driver_id": driver.id,
        "status": shipment.status.value
    }

# ------------------ UPDATE SHIPMENT STATUS ------------------

@app.post("/api/dispatcher/shipments/{shipment_id}/status")
async def update_shipment_status(
    shipment_id: int,
    update: ShipmentStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update shipment status"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    shipment.status = update.status
    db.commit()
    db.refresh(shipment)

    return {
        "message": "Shipment status updated successfully",
        "shipment_number": shipment.shipment_number,
        "new_status": shipment.status.value
    }

# ------------------ DRIVERS LIST ------------------

@app.get("/api/dispatcher/drivers")
async def list_drivers(db: Session = Depends(get_db)):
    """List all drivers"""
    drivers = db.query(Driver).all()

    return [
        {
            "id": d.id,
            "full_name": d.full_name,
            "phone": d.phone,
            "license_number": d.license_number
        }
        for d in drivers
    ]

# ------------------ RUN SERVER ------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.API_PORT_DISPATCHER,  # e.g. 8001
        reload=True
    )
