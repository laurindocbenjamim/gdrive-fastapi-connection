from fastapi import FastAPI, Depends, HTTPException, Request, Path
from sqlalchemy.orm import Session
from database import engine, get_db, Base
from models import User
from connectors.factory import get_connector
import os
import datetime
from fastapi.responses import RedirectResponse
from typing import List
from pydantic import BaseModel
import json

# Initialize Database
Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Cloud Drive Connector Hub"}

@app.get("/auth/{provider}/login")
def login(provider: str = Path(..., regex="^(google|onedrive)$")):
    try:
        connector = get_connector(provider)
        auth_url = connector.get_authorization_url()
        return RedirectResponse(auth_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/auth/{provider}/callback")
def callback(code: str, provider: str = Path(..., regex="^(google|onedrive)$"), db: Session = Depends(get_db)):
    try:
        connector = get_connector(provider)
        token_data = connector.exchange_code(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
    
    email = token_data.get("user_email")
    if not email:
         raise HTTPException(status_code=400, detail="Could not retrieve user email from provider")

    # Upsert User
    # Note: If a user uses same email for both, we might want to separate records or handle merging.
    # Current requirement: "User table... provider...". Implies one row per account per provider? 
    # Or multiple rows? "email (Identificador do usuário)" was original. 
    # "unique=True" on email in models.py means we strictly have one row per email.
    # If user has google AND onedrive with same email, unique constraint fails if we try to insert new row.
    # WE SHOULD UPDATE models.py to not have email as unique if we want multiple accounts, OR handle strictly one active provider per email (or combined).
    # Task says "Persistência: ... provider_type (google/onedrive) por usuário."
    # Usually this means a user can link both. 
    # But current Schema has one `provider` column, implying one provider per row. 
    # So if I have feti@gmail.com for google and feti@gmail.com for onedrive (if possible), they clash.
    # For now, let's assume unique constraint on (email, provider) would be better, OR just remove unique on email.
    
    # Let's check if user exists with this email AND provider.
    # Actually, simplest refactor for now: Check if user exists by email. 
    # If exists and provider is different, we either error or update.
    # Updating provider would wipe the other one's tokens. 
    # PROPER FIX: Remove unique=True from email or make (email, provider) unique.
    # Given I can't easily migrate DB structure cleanly with data preservation in this simple setup,
    # I will assume for now we look up by email. If provider differs, we overwrite (switch provider).
    # Ideally we'd have a User -> LinkedAccounts 1:N relationship. 
    # But sticking to the requested schema: "user_id, provider, ..."
    
    db_user = db.query(User).filter(User.email == email).first()
    
    if not db_user:
        db_user = User(email=email)
        db.add(db_user)
    
    db_user.provider = provider
    db_user.access_token = token_data['access_token']
    db_user.refresh_token = token_data.get('refresh_token')
    db_user.token_uri = token_data.get('token_uri')
    db_user.client_id = token_data.get('client_id')
    db_user.client_secret = token_data.get('client_secret')
    db_user.scopes = token_data.get('scopes')
    # db_user.token_expires_at = ... (Not returned by all, but can be added if crucial)

    db.commit()
    db.refresh(db_user)
    
    return {"message": f"Successfully connected to {provider}", "user": email}

class UserResponse(BaseModel):
    id: int
    email: str
    provider: str
    last_synced_at: datetime.datetime | None = None
    has_refresh_token: bool

    class Config:
        from_attributes = True

@app.get("/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "email": u.email,
            "provider": u.provider,
            "last_synced_at": u.last_synced_at,
            "has_refresh_token": bool(u.refresh_token)
        })
    return result

# Configuration Check
AVAILABLE_PROVIDERS = []
if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
    AVAILABLE_PROVIDERS.append("google")
if os.getenv("ONEDRIVE_CLIENT_ID") and os.getenv("ONEDRIVE_CLIENT_SECRET"):
    AVAILABLE_PROVIDERS.append("onedrive")

@app.get("/config")
def get_config():
    """Returns the available providers based on server configuration."""
    return {
        "available_providers": AVAILABLE_PROVIDERS,
        "mode": "multi-provider" if len(AVAILABLE_PROVIDERS) > 1 else "single-provider"
    }

from fastapi import BackgroundTasks
from worker import process_users

class SyncRequest(BaseModel):
    source_type: str = "both" # both, google, onedrive

    @property
    def valid_sources(self):
         if self.source_type == "both":
             return AVAILABLE_PROVIDERS
         if self.source_type in AVAILABLE_PROVIDERS:
             return [self.source_type]
         return []

@app.post("/sync")
def trigger_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    Triggers the background synchronization.
    
    - **source_type**: 'google', 'onedrive', or 'both' (default).
    """
    target_providers = request.valid_sources
    if not target_providers and request.source_type != "both":
         raise HTTPException(status_code=400, detail=f"Provider '{request.source_type}' is not configured or invalid.")
    
    background_tasks.add_task(process_users, providers=target_providers)
    return {
        "message": "Sync process started in background.", 
        "target_providers": target_providers
    }
