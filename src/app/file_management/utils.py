from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def async_get_or_create(session: AsyncSession, model, defaults=None, **kwargs):
    stmt = select(model).filter_by(**kwargs)
    result = await session.execute(stmt)
    instance = result.scalars().first()

    if instance:
        return instance, False

    kwargs |= defaults or {}
    instance = model(**kwargs)

    try:
        session.add(instance)
        await session.commit()
        return instance, True

    except IntegrityError:
        await session.rollback()
        result = await session.execute(stmt)
        instance = result.scalars().first()

        return instance, False
