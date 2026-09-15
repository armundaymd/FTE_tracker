"""
Create (or update) an admin user.

Usage — run from the backend/ directory so it picks up the same .env and
import paths as the app (`db.py`, `models/`):

    cd backend
    python -m scripts.create_admin

Reads ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_NAME from the environment (or a
.env file next to this one, same as the app); prompts for any that are
missing. If a user with that email already exists, updates its name,
password, and role to admin instead of creating a duplicate.

Non-interactive example (e.g. in a deploy step):

    ADMIN_EMAIL=admin@yourdomain.com \\
    ADMIN_PASSWORD='a-strong-password' \\
    ADMIN_NAME='Admin' \\
    python -m scripts.create_admin
"""

import asyncio
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from auth.security import hash_password  # noqa: E402
from db import AsyncSessionLocal  # noqa: E402
from models.user import User  # noqa: E402


def _prompt_email() -> str:
    email = os.environ.get("ADMIN_EMAIL")
    if email:
        return email
    while True:
        email = input("Admin email: ").strip()
        if email:
            return email
        print("Email cannot be empty.")


def _prompt_name() -> str:
    return os.environ.get("ADMIN_NAME") or input("Admin name [Admin]: ").strip() or "Admin"


def _prompt_password() -> str:
    password = os.environ.get("ADMIN_PASSWORD")
    if password:
        return password
    while True:
        password = getpass.getpass("Admin password: ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords did not match — try again.")
            continue
        return password


async def create_admin(email: str, name: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is not None:
            user.name = name
            user.hashed_password = hash_password(password)
            user.role = "admin"
            user.is_active = True
            await db.commit()
            print(f"Updated existing user '{email}' to admin.")
            return

        user = User(name=name, email=email, hashed_password=hash_password(password), role="admin")
        db.add(user)
        await db.commit()
        print(f"Created admin user '{email}'.")


def main() -> None:
    email = _prompt_email()
    name = _prompt_name()
    password = _prompt_password()
    asyncio.run(create_admin(email, name, password))


if __name__ == "__main__":
    main()
