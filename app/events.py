import time
from .logging import logger


def events_listener():
    from app import create_app
    app = create_app()
    app.app_context().push()
    
    while True:
        try:
            logger.warning("Waiting for requests")
            time.sleep(60)
          
        except Exception as e:
            sleep_sec = 60
            logger.exception(f"Exception in main block scanner loop: {e}")
            logger.warning(f"Waiting {sleep_sec} seconds before retry.")           
            time.sleep(sleep_sec)
 

