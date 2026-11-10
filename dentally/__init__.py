import sys
import os

# Ensure package directory is in sys.path for direct module imports
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

from .dentally_client import dentally_client, DentallyClient
from .dentally_service import (
    get_clinic_site_summary,
    fetch_dentally_free_slots,
    check_dentally_slots,
    list_upcoming_appointments
)

__all__ = [
    "dentally_client",
    "DentallyClient",
    "get_clinic_site_summary",
    "fetch_dentally_free_slots",
    "check_dentally_slots",
    "list_upcoming_appointments"
]
