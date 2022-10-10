from pydantic import BaseSettings


class Config(BaseSettings):
    admin: int
    post_to: int | str
    token: str
    user_country: str | None = None
