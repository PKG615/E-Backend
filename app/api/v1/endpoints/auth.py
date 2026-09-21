from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.core.security import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    create_refresh_token, 
    decode_token,
    oauth2_scheme
)
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, TokenResponse, UserResponse, RefreshTokenRequest
from app.schemas.common import APIResponse

router = APIRouter()

def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive or not found")
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not token:
        return None
    try:
        return get_current_user(token=token, db=db)
    except HTTPException:
        return None


def get_current_admin(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin account is inactive or not found")
    if user.role not in ["admin", "superadmin", "manager"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authorization required")
    return user

# RBAC Permissions Definitions
ADMIN_PERMISSIONS = {
    "superadmin": ["*"],
    "admin": ["*"],
    "manager": [
        "dashboard.read",
        "analytics.read",
        "analytics.export",
        "products.read", "products.create", "products.update",
        "inventory.read", "inventory.update",
        "orders.read", "orders.update",
        "payments.read",
        "shipments.read", "shipments.update",
        "returns.read", "returns.update",
        "refunds.read", "refunds.process",
        "replacements.read", "replacements.update",
        "coupons.read", "coupons.create", "coupons.update",
        "offers.read", "offers.create", "offers.update",
        "flash_sales.read", "flash_sales.create", "flash_sales.update",
        "reviews.read", "reviews.moderate",
        "questions.read", "questions.moderate",
        "customers.read", "customers.update",
        "support.read", "support.update",
    ],
    "customer": []
}

def check_permission(user: User, permission: str) -> bool:
    if not user or not user.is_active:
        return False
    user_perms = ADMIN_PERMISSIONS.get(user.role, [])
    if "*" in user_perms:
        return True
    return permission in user_perms

def require_permission(permission: str):
    def dependency(admin_user: User = Depends(get_current_admin)):
        if not check_permission(admin_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: permission '{permission}' required"
            )
        return admin_user
    return dependency

@router.post("/register", response_model=APIResponse[TokenResponse])
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing:
        return APIResponse(
            success=False,
            message="An account with this email already exists",
            error_code="EMAIL_ALREADY_EXISTS"
        )
    
    # Auto-grant admin role to admin@ecommerce.com or first user for frictionless platform bootstrapping
    role = "admin" if (user_in.email.lower().startswith("admin@") or db.query(User).count() == 0) else "customer"
    
    new_user = User(
        email=user_in.email.lower(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        phone=user_in.phone,
        role=role,
        is_active=True,
        is_verified=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(new_user.id, role=new_user.role)
    refresh_token = create_refresh_token(new_user.id, role=new_user.role)
    
    return APIResponse(
        success=True,
        message="Registration successful",
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.from_orm(new_user)
        )
    )

@router.post("/login", response_model=APIResponse[TokenResponse])
def login(login_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_in.email.lower()).first()
    if not user or not verify_password(login_in.password, user.hashed_password):
        return APIResponse(
            success=False,
            message="Invalid email or password",
            error_code="INVALID_CREDENTIALS"
        )
    
    if not user.is_active:
        return APIResponse(
            success=False,
            message="Account is disabled",
            error_code="ACCOUNT_DISABLED"
        )
    
    access_token = create_access_token(user.id, role=user.role)
    refresh_token = create_refresh_token(user.id, role=user.role)
    
    return APIResponse(
        success=True,
        message="Login successful",
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.from_orm(user)
        )
    )

@router.get("/me", response_model=APIResponse[UserResponse])
def get_me(current_user: User = Depends(get_current_user)):
    return APIResponse(
        success=True,
        message="User profile retrieved",
        data=UserResponse.from_orm(current_user)
    )

@router.post("/refresh", response_model=APIResponse[TokenResponse])
def refresh_access_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    user_id = decoded.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found"
        )
    
    new_access_token = create_access_token(user.id, role=user.role)
    new_refresh_token = create_refresh_token(user.id, role=user.role)
    return APIResponse(
        success=True,
        message="Token refreshed successfully",
        data=TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            user=UserResponse.from_orm(user)
        )
    )

@router.post("/logout", response_model=APIResponse[dict])
def logout():
    return APIResponse(
        success=True,
        message="Logged out successfully",
        data={"logged_out": True}
    )

