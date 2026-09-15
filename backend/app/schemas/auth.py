from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(description="Email or username")
    password: str


class TokenResponse(BaseModel):
    """Access token only — the refresh token is set as an httpOnly cookie."""

    access_token: str
    token_type: str = "bearer"
