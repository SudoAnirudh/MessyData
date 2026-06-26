import os
import time
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

# Set up logger
logger = logging.getLogger(__name__)

class TransientAPIException(Exception):
    """Exception raised for transient errors that warrant a retry (e.g., 429, 500, 503)."""
    pass

class SaaSAPIConnector:
    """Connector to extract contacts from the mock SaaS REST API with pagination, rate-limiting, and error tolerance."""

    def __init__(self, api_url: str = None):
        self.api_url = api_url or os.getenv("SAAS_API_URL", "http://mock-saas-api:8001")
        # Ensure url does not end with a slash
        if self.api_url.endswith("/"):
            self.api_url = self.api_url[:-1]

    @retry(
        retry=retry_if_exception_type(TransientAPIException),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def _fetch_page(self, url: str) -> dict:
        """Fetches a single page of contacts with retry logic for transient errors."""
        logger.debug(f"Fetching page: {url}")
        try:
            response = requests.get(url, timeout=5)
            
            # Handle rate limiting specifically
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "1")
                sleep_seconds = float(retry_after)
                logger.warning(f"Received HTTP 429 (Rate Limited). Respecting Retry-After: sleeping {sleep_seconds}s...")
                time.sleep(sleep_seconds)
                raise TransientAPIException("Rate limited by SaaS API")
                
            # Handle server-side transient errors
            if response.status_code in [500, 503]:
                logger.warning(f"Received HTTP {response.status_code} (Transient Server Error). Raising retry exception.")
                raise TransientAPIException(f"Transient server error: {response.status_code}")
                
            # For other non-200, raise standard HTTPError (will not be retried by TransientAPIException)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            # Catch network timeouts, connection drops and retry
            logger.warning(f"Network error encountered: {e}. Raising retry exception.")
            raise TransientAPIException(f"Network error: {e}")

    def extract(self) -> list[dict]:
        """Crawls all paginated pages from mock-saas-api and returns a consolidated contact list."""
        records = []
        next_url = f"{self.api_url}/api/v1/contacts?limit=50&offset=0"
        
        logger.info("Starting extraction from mock SaaS REST API...")
        try:
            while next_url:
                # If next_url is relative, prefix it with the API base URL
                if not next_url.startswith("http"):
                    next_url = f"{self.api_url}{next_url}"
                    
                data = self._fetch_page(next_url)
                
                contacts = data.get("contacts", [])
                records.extend(contacts)
                
                # Check for next page
                next_page_path = data.get("next_page")
                if next_page_path:
                    next_url = next_page_path
                    logger.debug(f"Moving to next page: {next_page_path}")
                else:
                    next_url = None
                    
            logger.info(f"Successfully extracted {len(records)} records from SaaS API.")
        except Exception as e:
            logger.error(f"Failed to crawl SaaS API: {e}")
            raise e
            
        return records
