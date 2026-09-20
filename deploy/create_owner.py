"""Provision the authorized owner without printing credentials."""
import asyncio
import os

from app.db import SessionFactory
from app.services.auth import register


async def main():
    async with SessionFactory() as session:
        await register(session, os.environ["APP_USER"], os.environ["APP_PASSWORD"])
    print("Owner account created")


asyncio.run(main())
