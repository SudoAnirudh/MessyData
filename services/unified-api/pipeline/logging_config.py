import logging
import json
import os

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def setup_logging(logger_name=None):
    use_json = os.getenv("STRUCTURED_LOGGING", "true").lower() in ("true", "1", "yes")
    
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    
    # Setup root logger to capture all module output
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing root handlers to avoid duplication
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
        
    handler = logging.StreamHandler()
    if use_json:
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ")
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    return logger

