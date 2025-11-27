"""Photo upload module."""

__version__ = "0.1.0"

# Import main components if you have them
# from .checker import IPhoneChecker
# from .utils import check_iphone

from .main import upload_photos_to_r2

__all__ = [
    "IPhoneChecker",
    # Add other exports here
]