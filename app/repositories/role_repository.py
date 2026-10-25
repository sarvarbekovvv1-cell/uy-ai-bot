"""Repository for Role and UserRole persistence and query operations."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import SYSTEM_ROLES, Role, UserRole


class RoleRepository:
    """Handles database access for Role entities and user role assignments."""

    async def get_by_name(self, session: AsyncSession, name: str) -> Role | None:
        """Fetch role by unique name."""
        stmt = select(Role).where(Role.name == name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def ensure_default_roles(self, session: AsyncSession) -> None:
        """Seed all system roles if they do not exist."""
        for role_name in SYSTEM_ROLES:
            existing = await self.get_by_name(session, role_name)
            if not existing:
                role = Role(name=role_name, description=f"System role: {role_name}")
                session.add(role)
        await session.flush()

    async def assign_role(
        self, session: AsyncSession, user_id: int, role_name: str
    ) -> UserRole | None:
        """Assign role to user if not already assigned."""
        role = await self.get_by_name(session, role_name)
        if not role:
            await self.ensure_default_roles(session)
            role = await self.get_by_name(session, role_name)
            if not role:
                return None

        # Check existing assignment
        stmt = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        result = await session.execute(stmt)
        existing_assignment = result.scalar_one_or_none()
        if existing_assignment:
            return existing_assignment

        user_role = UserRole(user_id=user_id, role_id=role.id)
        session.add(user_role)
        await session.flush()
        return user_role

    async def user_has_role(self, session: AsyncSession, user_id: int, role_name: str) -> bool:
        """Check whether a user has a specific role."""
        stmt = (
            select(UserRole.id)
            .join(Role, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, Role.name == role_name)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_user_roles(self, session: AsyncSession, user_id: int) -> list[str]:
        """Fetch all role names assigned to user."""
        stmt = (
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def remove_role(self, session: AsyncSession, user_id: int, role_name: str) -> bool:
        """Remove a role assignment from user."""
        role = await self.get_by_name(session, role_name)
        if not role:
            return False
        stmt = delete(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        result = await session.execute(stmt)
        await session.flush()
        return bool(result.rowcount and result.rowcount > 0)
