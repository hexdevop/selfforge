from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(description="Email or username")
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
