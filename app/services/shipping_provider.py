from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime

class BaseShippingProvider(ABC):
    """
    Abstract Base Class for Shipping Courier Providers.
    Provides standard interface for creating shipments, tracking,
    generating labels, and receiving webhook events.
    """

    @abstractmethod
    def create_shipment(
        self,
        order_number: str,
        destination_address: Dict[str, Any],
        items: list,
        shipping_method: str = "standard"
    ) -> Dict[str, Any]:
        """Request courier to generate AWB and register pickup."""
        pass

    @abstractmethod
    def get_tracking_status(self, tracking_number: str) -> Dict[str, Any]:
        """Fetch latest tracking milestone from courier API."""
        pass

    @abstractmethod
    def cancel_shipment(self, tracking_number: str) -> bool:
        """Cancel dispatch with courier."""
        pass


class InternalFulfillmentProvider(BaseShippingProvider):
    """
    Internal standard fulfillment provider.
    Used when external courier API credentials (e.g. Delhivery, Shiprocket, Blue Dart)
    are not configured in environment variables.
    Provides clean lifecycle transitions without synthesizing fake 3P courier API calls.
    """

    def __init__(self, carrier_name: Optional[str] = None):
        self.carrier_name = carrier_name or "Internal Fulfillment"

    def create_shipment(
        self,
        order_number: str,
        destination_address: Dict[str, Any],
        items: list,
        shipping_method: str = "standard"
    ) -> Dict[str, Any]:
        return {
            "provider": "internal",
            "carrier": self.carrier_name,
            "status": "pending",
            "tracking_number": None,
            "success": True
        }

    def get_tracking_status(self, tracking_number: str) -> Dict[str, Any]:
        return {
            "provider": "internal",
            "tracking_number": tracking_number,
            "events": []
        }

    def cancel_shipment(self, tracking_number: str) -> bool:
        return True


def get_shipping_provider(carrier: Optional[str] = None) -> BaseShippingProvider:
    """
    Provider factory. In the future, checks environment variables for
    courier API keys (e.g. DELHIVERY_API_KEY, SHIPROCKET_TOKEN) and returns
    the appropriate integration client. Defaults to InternalFulfillmentProvider.
    """
    return InternalFulfillmentProvider(carrier_name=carrier)
