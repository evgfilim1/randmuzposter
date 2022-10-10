from pydantic import BaseSettings


class Config(BaseSettings):
    admin: int
    post_to: int | str
    token: str
