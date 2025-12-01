"""
ODIN Market Feed Library
A Python Library for connecting to ODIN market feed WebSocket API for real-time trading data.
"""

from .MarketFeedClient import (
    ODINMarketFeedClient,
    ZLIBCompressor,
    FragmentationHandler
)

__version__ = "1.0.0"
__author__ = "SIPL"
__all__ = [
    "ODINMarketFeedClient",
    "ZLIBCompressor",
    "FragmentationHandler"
]
