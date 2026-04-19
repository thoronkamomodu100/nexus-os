from typing import Optional


def risky_operation(data) -> Optional[str]:
    """Perform uppercase conversion on data with error handling."""
    try:
        result = data.upper()
        return result
    except AttributeError:
        # Raised when data lacks .upper() method (e.g., None, int, list)
        return None


def another_risky() -> Optional[str]:
    """Get current working directory with error handling."""
    try:
        import os
        return os.getcwd()
    except OSError:
        # Raised for permission issues or missing environment
        return None
