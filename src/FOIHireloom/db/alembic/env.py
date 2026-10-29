from alembic import context

from FOIHireloom.config.settings import Settings
from FOIHireloom.db.alembic.environment import MigrationEnvironment


MigrationEnvironment(context.config, Settings()).run()
