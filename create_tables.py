from app.db.database import Base, engine
from app.models import user, roadmap
import logging

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)
logger.info("Tables created successfully.")