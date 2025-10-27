from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    # For MVP, using basic hardcoded authentication
    if request.username == "admin" and request.password == "phantom123":
        return TokenResponse(
            access_token="dummy-jwt-token",
            token_type="bearer"
        )
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )

@router.post("/logout")
async def logout():
    return {"message": "Logged out successfully"}

@router.get("/me")
async def get_current_user():
    # For MVP, return basic user info
    return {
        "id": 1,
        "username": "admin",
        "email": "admin@phantom-security.ai"
    }