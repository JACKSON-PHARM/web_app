"""
Authentication API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import timedelta
from app.config import settings
from app.dependencies import get_current_user, get_user_service
from app.security import create_access_token

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    is_admin: bool
    days_remaining: int

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    """Login with username and password"""
    username = login_data.username.strip()
    password = login_data.password
    
    # Authenticate user
    user_service = get_user_service()
    user = user_service.authenticate(username, password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password, or subscription expired."
        )
    
    # Calculate days remaining
    days_remaining = 0
    if user.get('subscription_expires'):
        from datetime import datetime
        try:
            expires = datetime.fromisoformat(user['subscription_expires'])
            days_remaining = max(0, (expires - datetime.now()).days)
        except:
            pass
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": username, "is_admin": user['is_admin']},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user['username'],
        "is_admin": user['is_admin'],
        "days_remaining": days_remaining
    }

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout (client-side token removal)"""
    return {"message": "Logged out successfully"}

@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    return {
        "username": current_user.get("username", ""),
        "is_admin": current_user.get("is_admin", False)
    }

