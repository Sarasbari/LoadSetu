import logging
from services import supabase_service

logger = logging.getLogger(__name__)

def log_event(shipment_id: str = None, phone_number: str = None, event_type: str = "", title: str = "", description: str = None, metadata: dict = None):
    """Logs an audit event to the timeline for a given shipment."""
    logger.info(f"Timeline event [{event_type}]: {title} - {description}")
    return supabase_service.create_timeline_event(
        shipment_id=shipment_id,
        phone_number=phone_number,
        event_type=event_type,
        title=title,
        description=description,
        metadata=metadata
    )
