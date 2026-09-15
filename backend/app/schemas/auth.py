from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    login: str = Field(description="Email or username")
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """Access token only — the refresh token is set as an httpOnly cookie."""

    access_token: str
    token_type: str = "bearer"
