import asyncpg
from dataclasses import dataclass
from datetime import datetime

class Database:

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        if not self.pool:
            self.pool = await asyncpg.create_pool(self.dsn)

    async def close(self):
        if self.pool:
            await self.pool.close()

@dataclass
class RuntimeConfig:
    enabled: bool = True
    last_promoted: datetime | None = None
    pro: bool = False


class RuntimeManager:
    def __init__(self, db: Database):
        self.db = db
        self.cache: dict[int, RuntimeConfig] = {}

    async def setup(self):
        await self.db.pool.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_config (
                guild_id BIGINT PRIMARY KEY,
                enabled  BOOLEAN NOT NULL DEFAULT TRUE,
                last_promoted TIMESTAMPTZ NULL,
                pro BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )

    async def load_cache(self):
        rows = await self.db.pool.fetch(
            "SELECT guild_id, enabled, last_promoted, pro FROM runtime_config"
        )
        self.cache = {
            r["guild_id"]: RuntimeConfig(
                enabled=r["enabled"],
                last_promoted=r["last_promoted"],
                pro=r["pro"]
            )
            for r in rows
        }

    def is_enabled(self, guild_id: int) -> bool:
        return self.cache.get(guild_id, RuntimeConfig()).enabled

    def is_pro_enabled(self, guild_id: int) -> bool:
        return self.cache.get(guild_id, RuntimeConfig()).pro

    def get_last_promoted(self, guild_id: int):
        return self.cache.get(guild_id, RuntimeConfig()).last_promoted

    async def set_enabled(self, guild_id: int, value: bool):
        await self.db.pool.execute(
            """
            INSERT INTO runtime_config (guild_id, enabled)
            VALUES ($1, $2)
            ON CONFLICT (guild_id)
            DO UPDATE SET enabled = EXCLUDED.enabled
            """,
            guild_id,
            value,
        )
        config = self.cache.setdefault(guild_id, RuntimeConfig())
        config.enabled = value

    async def set_pro(self, guild_id: int, value: bool):
        await self.db.pool.execute(
            """
            INSERT INTO runtime_config (guild_id, pro)
            VALUES ($1, $2)
            ON CONFLICT (guild_id)
            DO UPDATE SET pro = EXCLUDED.pro
            """,
            guild_id,
            value,
        )

        config = self.cache.setdefault(guild_id, RuntimeConfig())
        config.pro = value

    async def set_last_promoted(self, guild_id: int, timestamp):
        await self.db.pool.execute(
            """
            INSERT INTO runtime_config (guild_id, last_promoted)
            VALUES ($1, $2)
            ON CONFLICT (guild_id)
            DO UPDATE SET last_promoted = EXCLUDED.last_promoted
            """,
            guild_id,
            timestamp
        )

        config = self.cache.setdefault(guild_id, RuntimeConfig())
        config.last_promoted = timestamp
