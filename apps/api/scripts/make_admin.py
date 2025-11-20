"""Utility script to promote a user to admin."""

import argparse
import os
import sys

from sqlmodel import Session, select

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import engine  # noqa: E402
from models import User  # noqa: E402


def make_admin(email: str) -> bool:
    normalized = email.strip().lower()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == normalized)).first()
        if not user:
            return False
        user.is_admin = True
        session.add(user)
        session.commit()
        return True


def main():
    parser = argparse.ArgumentParser(description="Promote a Consultaion user to admin.")
    parser.add_argument("email", nargs="?", help="Email address of the user to promote.")
    args = parser.parse_args()
    email = args.email or os.getenv("ADMIN_EMAIL")
    if not email:
        parser.error("Email argument or ADMIN_EMAIL environment variable is required.")
    if make_admin(email):
        print(f"User {email} promoted to admin.")
    else:
        print(f"User {email} not found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
