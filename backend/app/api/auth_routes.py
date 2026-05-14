from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.schemas.user_schema import LoginRequest, UserRead
from app.services.auth_service import authenticate_user, create_access_token, get_current_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Kullanici adi/e-posta veya sifre hatali.")
    token = create_access_token(user.username)
    return ok({"access_token": token, "token_type": "bearer", "user": UserRead.model_validate(user).model_dump(mode="json")}, "Giris basarili.")


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return ok(UserRead.model_validate(current_user).model_dump(mode="json"))


@router.post("/logout")
def logout():
    return ok(message="JWT stateless oldugu icin istemci tokeni silmelidir.")

