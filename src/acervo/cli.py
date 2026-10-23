"""`uv run python -m acervo.cli reindex <kb_id>`: asks for the index of every file and page of a base, for data
from before indexing existed; the worker builds them."""

import asyncio
import sys
from uuid import UUID

from acervo.core.settings import get_settings
from acervo.db.session import create_engine, create_session_factory
from acervo.repositories.uow import UnitOfWork
from acervo.services.index_service import request


async def reindex(kb_id: UUID) -> int:
    engine = create_engine(get_settings())
    try:
        async with UnitOfWork(create_session_factory(engine)) as uow:
            nodes = [node for node in await uow.nodes.live_in(kb_id) if node.kind != "folder"]
            for node in nodes:
                await request(uow, node)
            await uow.commit()
    finally:
        await engine.dispose()
    return len(nodes)


def main() -> None:
    match sys.argv[1:]:
        case ["reindex", kb_id]:
            print(f"{asyncio.run(reindex(UUID(kb_id)))} files and pages queued for indexing")
        case _:
            sys.exit("usage: python -m acervo.cli reindex <kb_id>")


if __name__ == "__main__":
    main()
