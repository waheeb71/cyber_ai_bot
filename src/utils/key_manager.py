import logging
import itertools
from typing import List, Optional

logger = logging.getLogger(__name__)

class KeyManager:
    def __init__(self, keys: List[str]):
        if not keys:
            logger.warning("KeyManager initialized with no keys!")
            self._keys = []
            self._cycle = None
        else:
            self._keys = keys
            # Create a cycling iterator
            self._cycle = itertools.cycle(self._keys)
            self._current_key = next(self._cycle)
            logger.info(f"KeyManager initialized with {len(keys)} keys.")

    def get_current_key(self) -> Optional[str]:
        """Returns the current active key."""
        return self._current_key

    def rotate_key(self) -> Optional[str]:
        """Switch to the next key in the list."""
        if not self._cycle:
            return None
            
        prev_key = self._current_key
        self._current_key = next(self._cycle)
        
        # Don't log the full key for security
        masked_prev = f"{prev_key[:4]}...{prev_key[-4:]}" if prev_key else "None"
        masked_new = f"{self._current_key[:4]}...{self._current_key[-4:]}" if self._current_key else "None"
        
        logger.info(f"Rotating API Key: {masked_prev} -> {masked_new}")
        return self._current_key

    def report_error(self, key: str):
        """Report an error with the current key (triggering rotation implies this)."""
        # For now, we just rotate on error. detailed stats could be added later.
        if key == self._current_key:
            self.rotate_key()
