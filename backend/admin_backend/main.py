"""
Dispatcher Backend API - Fully OOP Design
Features:
- Dispatcher login & JWT auth
- Full shipment management
- Driver assignment
- Status updates
- Send messages/notifications to Customer or Driver
- View sent message history
"""

import sys
from pathlib import Path
# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Literal
from datetime import datetime

from backend.shared.database import get_db, engine, Base
from backend.shared.models import (
    User, Shipment, Driver, Message, ShipmentStatus, UserRole, MessageType
)
from backend.shared.utils import verify_password, create_access_token, get_current_user
from backend.shared.config import settings


# =============================================================================
#                               OOP SERVICES
# =============================================================================

class AuthService:
    @staticmethod
    def authenticate_dispatcher(email: str, password: str, db: Session) -> User:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        # role may be stored as an Enum or as a raw value; handle both safely
        role_value = getattr(user.role, 'value', user.role)
        if role_value != "dispatcher":
            raise HTTPException(status_code=403, detail="Dispatcher access only")
        
        # Update the login timestamp in database
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        return user

    @staticmethod
    def create_token(user: User) -> dict:
        token = create_access_token(data={"sub": user.email, "role": user.role.value})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "role": user.role.value
            }
        }


class ShipmentService:
    @staticmethod
    def list_shipments(status: Optional[ShipmentStatus], db: Session) -> List[dict]:
        query = db.query(Shipment)\
            .join(User, Shipment.customer_id == User.id, isouter=True)\
            .join(Driver, Shipment.driver_id == Driver.id, isouter=True)

        if status:
            query = query.filter(Shipment.status == status)

        shipments = query.all()
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
                "customer_name": s.customer.full_name if s.customer else "—",
                "driver_name": s.driver.full_name if s.driver else "Not assigned",
                "created_at": s.created_at.isoformat()
            }
            for s in shipments
        ]

    @staticmethod
    def get_shipment_detail(shipment_id: int, db: Session) -> dict:
        shipment = db.query(Shipment)\
            .join(User, Shipment.customer_id == User.id, isouter=True)\
            .join(Driver, Shipment.driver_id == Driver.id, isouter=True)\
            .filter(Shipment.id == shipment_id).first()

        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        return {
            "id": shipment.id,
            "shipment_number": shipment.shipment_number,
            "pickup_location": shipment.pickup_location,
            "delivery_location": shipment.delivery_location,
            "status": shipment.status.value,
            "customer": {
                "id": shipment.customer.id,
                "name": shipment.customer.full_name,
                "phone": shipment.customer.phone
            } if shipment.customer else None,
            "driver": {
                "id": shipment.driver.id,
                "name": shipment.driver.full_name,
                "phone": shipment.driver.phone
            } if shipment.driver else None,
            "created_at": shipment.created_at.isoformat()
        }

    @staticmethod
    def assign_driver(shipment_id: int, driver_id: int, db: Session) -> dict:
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        driver = db.query(Driver).filter(Driver.id == driver_id).first()

        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")

        shipment.driver_id = driver.id
        shipment.status = ShipmentStatus.ASSIGNED
        db.commit()

        return {
            "message": "Driver assigned",
            "shipment_number": shipment.shipment_number,
            "driver": driver.full_name,
            "status": "ASSIGNED"
        }

    @staticmethod
    def update_status(shipment_id: int, new_status: ShipmentStatus, db: Session) -> dict:
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        shipment.status = new_status
        db.commit()

        return {
            "message": "Status updated",
            "shipment_number": shipment.shipment_number,
            "new_status": new_status.value
        }


class NotificationService:
    """Handles sending messages from dispatcher to customer/driver"""

    @staticmethod
    def send_message(
        sender: User,
        recipient_id: int,
        message: str,
        shipment_id: Optional[int],
        message_type: MessageType,
        db: Session
    ) -> dict:
        recipient = db.query(User).filter(User.id == recipient_id).first()
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")
        # Message model uses `content` for the message body and an Enum for message_type
        new_msg = Message(
            sender_id=sender.id,
            recipient_id=recipient_id,
            shipment_id=shipment_id,
            content=message,
            message_type=message_type
        )
        db.add(new_msg)
        db.commit()
        db.refresh(new_msg)

        return {
            "id": new_msg.id,
            "content": message,
            "sent_to": recipient.full_name,
            "sent_to_role": recipient.role.value,
            "shipment_id": shipment_id,
            "sent_at": new_msg.created_at.isoformat()
        }

    @staticmethod
    def get_sent_messages(dispatcher: User, db: Session) -> List[dict]:
        messages = db.query(Message).filter(Message.sender_id == dispatcher.id).all()
        return [
            {
                "id": m.id,
                "content": m.content,
                "to": m.recipient.full_name,
                "to_role": m.recipient.role.value,
                "shipment_number": m.shipment.shipment_number if m.shipment else None,
                "sent_at": m.created_at.isoformat(),
                "is_read": m.is_read
            }
            for m in messages
        ]


class DriverService:
    @staticmethod
    def list_drivers(db: Session) -> List[dict]:
        drivers = db.query(Driver).all()
        return [
            {
                "id": d.id,
                "full_name": d.full_name,
                "phone": d.phone,
                "license_number": d.license_number,
                "status": "Available"  # You can enhance with real status later
            }
            for d in drivers
        ]


# =============================================================================
#                               FASTAPI APP FACTORY
# =============================================================================

def create_app() -> FastAPI:
    app = FastAPI(
        title="Logistics - Dispatcher Panel API",
        description="Full dispatcher dashboard with messaging & notifications",
        version="2.0.0"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/dispatcher/login")

    def get_current_dispatcher(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
    ):
        user = get_current_user(token, db)
        if user.role != UserRole.DISPATCHER:
            raise HTTPException(status_code=403, detail="Dispatcher access required")
        return user


    # ================================ ROUTES ================================

    @app.get("/")
    async def root():
        return {"message": "Dispatcher Panel API", "status": "running"}

    class LoginRequest(BaseModel):
        email: EmailStr
        password: str

    @app.post("/api/dispatcher/login")
    async def login(payload: LoginRequest, db: Session = Depends(get_db)):
        user = AuthService.authenticate_dispatcher(payload.email, payload.password, db)
        return AuthService.create_token(user)

    @app.get("/api/dispatcher/shipments")
    async def list_shipments(
        status: Optional[ShipmentStatus] = None,
        db: Session = Depends(get_db),
        current: User = Depends(get_current_dispatcher)
    ):
        return ShipmentService.list_shipments(status, db)

    @app.get("/api/dispatcher/shipments/{shipment_id}")
    async def shipment_detail(
        shipment_id: int,
        db: Session = Depends(get_db),
        current: User = Depends(get_current_dispatcher)
    ):
        return ShipmentService.get_shipment_detail(shipment_id, db)

    @app.post("/api/dispatcher/shipments/{shipment_id}/assign")
    async def assign_driver(
        shipment_id: int,
        driver_id: int,
        db: Session = Depends(get_db),
        current: User = Depends(get_current_dispatcher)
    ):
        return ShipmentService.assign_driver(shipment_id, driver_id, db)

    @app.post("/api/dispatcher/shipments/{shipment_id}/status")
    async def update_status(
        shipment_id: int,
        status: ShipmentStatus,
        db: Session = Depends(get_db),
        current: User = Depends(get_current_dispatcher)
    ):
        return ShipmentService.update_status(shipment_id, status, db)

    @app.get("/api/dispatcher/drivers")
    async def list_drivers(
        db: Session = Depends(get_db),
        current: User = Depends(get_current_dispatcher)
    ):
        return DriverService.list_drivers(db)

    # ================================ NOTIFICATIONS ===============================

    class MessageCreate(BaseModel):
        recipient_id: int
        message: str
        shipment_id: Optional[int] = None
        message_type: Literal["to_customer", "to_driver"]

    @app.post("/api/dispatcher/messages/send")
    async def send_message(
        payload: MessageCreate,
        current: User = Depends(get_current_dispatcher),
        db: Session = Depends(get_db)
    ):
        msg_type = MessageType.TO_CUSTOMER if payload.message_type == "to_customer" else MessageType.TO_DRIVER
        return NotificationService.send_message(
            sender=current,
            recipient_id=payload.recipient_id,
            message=payload.message,
            shipment_id=payload.shipment_id,
            message_type=msg_type,
            db=db
        )

    @app.get("/api/dispatcher/messages/sent")
    async def sent_messages(
        current: User = Depends(get_current_dispatcher),
        db: Session = Depends(get_db)
    ):
        return NotificationService.get_sent_messages(current, db)

    return app

Base.metadata.create_all(bind=engine)
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.API_PORT_ADMIN or 8003,
        reload=False
    )
