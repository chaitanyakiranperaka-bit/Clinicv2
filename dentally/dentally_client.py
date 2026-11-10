import json
import time
import ssl
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, List

try:
    from .dentally_config import (
        DENTALLY_BASE_URL,
        DENTALLY_AUTH_URL,
        DENTALLY_CLIENT_ID,
        DENTALLY_CLIENT_SECRET,
        DENTALLY_PRACTICE_ID,
        DENTALLY_API_VERSION
    )
except ImportError:
    from dentally_config import (
        DENTALLY_BASE_URL,
        DENTALLY_AUTH_URL,
        DENTALLY_CLIENT_ID,
        DENTALLY_CLIENT_SECRET,
        DENTALLY_PRACTICE_ID,
        DENTALLY_API_VERSION
    )

class DentallyClient:
    """Production-grade client for the Dentally NexGen REST API (v2026-01-01).
    STRICTLY READ-ONLY ACCESS.
    
    Handles OAuth 2.0 Client Credentials token management, automatic refresh,
    and API calls scoped to the clinic's practice ID.
    """
    
    def __init__(
        self,
        base_url: str = DENTALLY_BASE_URL,
        auth_url: str = DENTALLY_AUTH_URL,
        client_id: str = DENTALLY_CLIENT_ID,
        client_secret: str = DENTALLY_CLIENT_SECRET,
        practice_id: str = DENTALLY_PRACTICE_ID,
        api_version: str = DENTALLY_API_VERSION
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_url = auth_url
        self.client_id = client_id.strip() if client_id else ""
        self.client_secret = client_secret.strip() if client_secret else ""
        self.practice_id = practice_id.strip() if practice_id else ""
        self.api_version = api_version
        
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._ssl_context = ssl.create_default_context()
        self._cached_site: Optional[Dict[str, Any]] = None

    def is_configured(self) -> bool:
        """Returns True if minimum required credentials and practice ID are set."""
        return bool(self.client_id and self.client_secret and self.practice_id)

    def get_token(self) -> str:
        """Retrieves a valid OAuth2 Bearer token, refreshing if within 300s of expiry."""
        now = time.time()
        if self._token and now < (self._token_expires_at - 300):
            return self._token

        if not self.is_configured():
            raise ValueError("DentallyClient credentials or practice ID not configured.")

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": self.base_url
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.auth_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "StarClinicDentallyClient/1.0"
            }
        )

        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                self._token = body.get("access_token")
                expires_in = int(body.get("expires_in", 86400))
                self._token_expires_at = now + expires_in
                return self._token
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            print(f"[Dentally Auth Error {e.code}]: {err_msg}", flush=True)
            raise RuntimeError(f"Dentally OAuth authentication failed ({e.code}): {err_msg}")
        except Exception as e:
            print(f"[Dentally Auth Network Error]: {e}", flush=True)
            raise RuntimeError(f"Dentally OAuth request failed: {e}")

    def _read_request(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 10
    ) -> Dict[str, Any]:
        """Makes an authenticated READ (GET) request to the Dentally NexGen API."""
        token = self.get_token()
        
        # Ensure path begins with /v2
        clean_path = path if path.startswith("/v2/") else f"/v2/{path.lstrip('/')}"
        url = f"{self.base_url}{clean_path}"
        
        if params:
            # Handle list params e.g. practitioner_ids[]
            encoded_pairs = []
            for k, v in params.items():
                if isinstance(v, (list, tuple)):
                    for item in v:
                        encoded_pairs.append((f"{k}[]" if not k.endswith("[]") else k, str(item)))
                else:
                    encoded_pairs.append((k, str(v)))
            query_str = urllib.parse.urlencode(encoded_pairs)
            url = f"{url}?{query_str}" if query_str else url

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Practice-Id": self.practice_id,
            "Dentally-API-Version": self.api_version,
            "Content-Type": "application/json",
            "User-Agent": "StarClinicDentallyClient/1.0"
        }

        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=timeout) as resp:
                resp_text = resp.read().decode("utf-8")
                return json.loads(resp_text) if resp_text else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"[Dentally API Error {e.code} on GET {url}]: {err_body}", flush=True)
            raise RuntimeError(f"Dentally API error ({e.code}): {err_body}")
        except Exception as e:
            print(f"[Dentally Network Error on GET {url}]: {e}", flush=True)
            raise RuntimeError(f"Dentally connection error: {e}")

    # =========================================================================
    # READ ENDPOINTS ONLY (NO WRITE)
    # =========================================================================

    def get_sites(self) -> List[Dict[str, Any]]:
        """GET /v2/sites: Returns practice sites, addresses, and opening hours."""
        res = self._read_request("/sites")
        return res.get("data", [])

    def get_primary_site(self) -> Optional[Dict[str, Any]]:
        """Returns the primary practice site, cached after first read."""
        if self._cached_site:
            return self._cached_site
        sites = self.get_sites()
        if sites:
            self._cached_site = sites[0]
            return self._cached_site
        return None

    def get_practitioner_availability(
        self,
        date_from: str,
        date_to: str,
        practitioner_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """GET /v2/practitioners/availabilities: Queries bookable availability windows.
        
        Args:
            date_from: YYYY-MM-DD
            date_to: YYYY-MM-DD (must be within 7 days of date_from)
            practitioner_ids: list of practitioner UUIDs
        Returns:
            List of slot windows, each with practitioner_id, start_time, finish_time (UTC).
        """
        params = {
            "date_from": date_from,
            "date_to": date_to,
            "practitioner_ids": practitioner_ids
        }
        res = self._read_request("/practitioners/availabilities", params=params)
        return res.get("data", [])

    def get_appointments(self, limit: int = 20, cursor: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/appointments: Retrieves recent/upcoming appointments."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._read_request("/appointments", params=params)

    def get_appointment_reasons(self) -> List[Dict[str, Any]]:
        """GET /v2/appointment_reasons: Returns practice clinical visit reasons."""
        res = self._read_request("/appointment_reasons")
        return res.get("data", [])

    def get_calendar_zones(self, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """GET /v2/calendar_zones: Returns calendar zone blocks for date range."""
        params = {"date_from": date_from, "date_to": date_to}
        res = self._read_request("/calendar_zones", params=params)
        return res.get("data", [])

# Global singleton client instance
dentally_client = DentallyClient()

