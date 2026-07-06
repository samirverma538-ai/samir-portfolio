from fastapi import HTTPException

from config import ADMIN_PASSWORD


def verify_admin(password: str) -> None:
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid admin password")
