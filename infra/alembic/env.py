import os, sys 
from logging.config import fileConfig 
from sqlalchemy import engine_from_config, pool 
from alembic import context 
 
# Añade el repo root al sys.path 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))) 
 
# Importa settings y Base
from backend.app.core.settings import settings 
from backend.app.db.session import Base 

# Importación directa de todos los modelos
from backend.app.models import *  # Esto importa Order y cualquier otro modelo

config = context.config 
if config.config_file_name is not None: 
    fileConfig(config.config_file_name) 

db_url = settings.sync_database_url 
if not db_url: 
    # fallback: deriva de la async reemplazando el driver 
    db_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg") 
 
# Sobrescribe la opción principal de Alembic 
config.set_main_option("sqlalchemy.url", db_url) 
 
target_metadata = Base.metadata 

def run_migrations_offline(): 
    url = config.get_main_option("sqlalchemy.url") 
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}) 
    with context.begin_transaction(): 
        context.run_migrations() 
 
def run_migrations_online(): 
    connectable = engine_from_config( 
        config.get_section(config.config_ini_section), 
        prefix="sqlalchemy.", 
        poolclass=pool.NullPool, 
    ) 
    with connectable.connect() as connection: 
        context.configure(connection=connection, target_metadata=target_metadata) 
        with context.begin_transaction(): 
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()