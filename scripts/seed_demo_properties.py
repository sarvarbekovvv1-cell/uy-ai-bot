"""Seed sample approved properties with Tashkent coordinates for Mini App testing."""

import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.database.session import get_session_factory
from app.models.property import Property
from app.models.user import User

DEMO_PROPERTIES = [
    {
        "title": "3 xonali shinam kvartira, Oybek metrosi",
        "listing_type": "sale",
        "property_type": "apartment",
        "description": (
            "Oybek metrosi yaqinida joylashgan 3 xonali ta’mirlangan kvartira. "
            "Barcha qulayliklar bor."
        ),
        "region": "Toshkent shahri",
        "district": "Mirobod",
        "address": "Oybek ko‘chasi, 24-uy",
        "latitude": Decimal("41.2965000"),
        "longitude": Decimal("69.2721000"),
        "rooms": 3,
        "total_area": Decimal("85.00"),
        "living_area": Decimal("55.00"),
        "floor": 4,
        "total_floors": 9,
        "condition": "renovated",
        "has_furniture": True,
        "cadastre_status": "available",
        "price": Decimal("92000.00"),
        "currency": "USD",
        "status": "approved",
    },
    {
        "title": "Yangi ta’mirlangan 2 xonali uy, Yunusobod 4-mavze",
        "listing_type": "sale",
        "property_type": "apartment",
        "description": (
            "Yunusobod 4-mavzeda joylashgan, metroga 5 daqiqalik yo‘l. "
            "Maktab va bog‘cha yaqin."
        ),
        "region": "Toshkent shahri",
        "district": "Yunusobod",
        "address": "Amir Temur shoh ko‘chasi",
        "latitude": Decimal("41.3532000"),
        "longitude": Decimal("69.2885000"),
        "rooms": 2,
        "total_area": Decimal("62.00"),
        "living_area": Decimal("40.00"),
        "floor": 3,
        "total_floors": 5,
        "condition": "renovated",
        "has_furniture": True,
        "cadastre_status": "available",
        "price": Decimal("68000.00"),
        "currency": "USD",
        "status": "approved",
    },
    {
        "title": "Chilonzor 7-mavzeda 1 xonali kvartira (Ijara)",
        "listing_type": "rent",
        "property_type": "apartment",
        "description": "Uzoq muddatga oilaga ijaraga beriladi. Barcha maishiy texnikalar mavjud.",
        "region": "Toshkent shahri",
        "district": "Chilonzor",
        "address": "Chilonzor 7-mavze",
        "latitude": Decimal("41.2825000"),
        "longitude": Decimal("69.2085000"),
        "rooms": 1,
        "total_area": Decimal("42.00"),
        "living_area": Decimal("24.00"),
        "floor": 2,
        "total_floors": 4,
        "condition": "renovated",
        "has_furniture": True,
        "cadastre_status": "available",
        "price": Decimal("450.00"),
        "currency": "USD",
        "status": "approved",
    },
    {
        "title": "Mirzo Ulug‘bekda 4 xonali zamonaviy kvartira",
        "listing_type": "sale",
        "property_type": "apartment",
        "description": "Buyuk Ipak Yo‘li metrosi yaqinida elita uyda 4 xonali kvartira.",
        "region": "Toshkent shahri",
        "district": "Mirzo Ulug‘bek",
        "address": "Buyuk Ipak Yo‘li ko‘chasi",
        "latitude": Decimal("41.3256000"),
        "longitude": Decimal("69.3245000"),
        "rooms": 4,
        "total_area": Decimal("125.00"),
        "living_area": Decimal("85.00"),
        "floor": 7,
        "total_floors": 12,
        "condition": "renovated",
        "has_furniture": True,
        "cadastre_status": "available",
        "price": Decimal("145000.00"),
        "currency": "USD",
        "status": "approved",
    },
]


async def seed() -> None:
    factory = get_session_factory()
    async with factory() as session:
        # Find first owner user
        user = (await session.execute(select(User))).scalars().first()
        if not user:
            print("No users found in database.")
            return

        # Update existing property 1 if it has no coords
        prop1 = (await session.execute(select(Property))).scalars().first()
        if prop1 and not prop1.latitude:
            prop1.latitude = Decimal("41.3111000")
            prop1.longitude = Decimal("69.2797000")
            prop1.district = prop1.district or "Mirobod"
            prop1.region = prop1.region or "Toshkent shahri"
            print(f"Updated Property #{prop1.id} with coordinates.")

        # Check existing count
        existing = (await session.execute(select(Property))).scalars().all()
        if len(existing) < 4:
            for data in DEMO_PROPERTIES:
                p = Property(owner_user_id=user.id, **data)
                session.add(p)
            await session.commit()
            print("Added demo properties for Mini App.")
        else:
            await session.commit()
            print("Database already has properties.")


if __name__ == "__main__":
    asyncio.run(seed())
