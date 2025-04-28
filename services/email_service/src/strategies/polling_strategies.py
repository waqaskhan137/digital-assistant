from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Define constants for thresholds and intervals
HIGH_VOLUME_THRESHOLD = 50  # Emails per sync cycle
LOW_VOLUME_THRESHOLD = 10   # Emails per sync cycle
HIGH_VOLUME_INTERVAL_MINUTES = 2
MEDIUM_VOLUME_INTERVAL_MINUTES = 5
LOW_VOLUME_INTERVAL_MINUTES = 15
DEFAULT_INTERVAL_MINUTES = 5
MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 60

class PollingStrategy(ABC):
    """Abstract base class for polling interval calculation strategies."""

    @abstractmethod
    def calculate_interval(
        self,
        user_id: str,
        sync_metrics: Optional[Dict[str, Any]],
        current_interval: int,
        user_preference_minutes: Optional[int] = None
    ) -> int:
        """Calculates the optimal polling interval in minutes."""
        pass

class FixedPollingStrategy(PollingStrategy):
    """A simple strategy that returns a fixed polling interval."""

    def __init__(self, interval_minutes: int = DEFAULT_INTERVAL_MINUTES):
        self._interval = max(MIN_INTERVAL_MINUTES, min(interval_minutes, MAX_INTERVAL_MINUTES))
        logger.info(f"Initialized FixedPollingStrategy with interval: {self._interval} minutes")

    def calculate_interval(
        self,
        user_id: str,
        sync_metrics: Optional[Dict[str, Any]],
        current_interval: int,
        user_preference_minutes: Optional[int] = None
    ) -> int:
        """Returns the fixed interval, respecting user preference if provided."""
        interval = user_preference_minutes if user_preference_minutes is not None else self._interval
        final_interval = max(MIN_INTERVAL_MINUTES, min(interval, MAX_INTERVAL_MINUTES))
        logger.debug(f"FixedPollingStrategy returning interval: {final_interval} minutes for user {user_id}")
        return final_interval


class AdaptivePollingStrategy(PollingStrategy):
    """Calculates polling interval based on recent email volume."""

    def calculate_interval(
        self,
        user_id: str,
        sync_metrics: Optional[Dict[str, Any]],
        current_interval: int,
        user_preference_minutes: Optional[int] = None
    ) -> int:
        """
        Calculates the optimal polling interval based on email volume.

        Args:
            user_id: The ID of the user.
            sync_metrics: Dictionary containing sync metrics like 'emails_processed'.
            current_interval: The current polling interval in minutes.
            user_preference_minutes: Optional user-defined interval preference.

        Returns:
            The calculated optimal polling interval in minutes.
        """
        if user_preference_minutes is not None:
            preferred = max(MIN_INTERVAL_MINUTES, min(user_preference_minutes, MAX_INTERVAL_MINUTES))
            logger.info(f"User {user_id} preference set: Using interval {preferred} minutes.")
            return preferred

        if not sync_metrics or 'emails_processed' not in sync_metrics:
            logger.warning(f"No sync metrics available for user {user_id}. Using default interval: {DEFAULT_INTERVAL_MINUTES} minutes.")
            return DEFAULT_INTERVAL_MINUTES

        emails_processed = sync_metrics.get('emails_processed', 0)
        last_sync_duration = sync_metrics.get('duration_seconds', 0) # Assuming duration is available

        # Basic volume-based adjustment
        if emails_processed > HIGH_VOLUME_THRESHOLD:
            calculated_interval = HIGH_VOLUME_INTERVAL_MINUTES
            logger.info(f"User {user_id}: High email volume ({emails_processed}). Setting interval to {calculated_interval} minutes.")
        elif emails_processed < LOW_VOLUME_THRESHOLD:
            calculated_interval = LOW_VOLUME_INTERVAL_MINUTES
            logger.info(f"User {user_id}: Low email volume ({emails_processed}). Setting interval to {calculated_interval} minutes.")
        else:
            calculated_interval = MEDIUM_VOLUME_INTERVAL_MINUTES
            logger.info(f"User {user_id}: Medium email volume ({emails_processed}). Setting interval to {calculated_interval} minutes.")

        # TODO: Consider adding more sophisticated logic, e.g., based on sync duration

        # Ensure interval is within bounds
        final_interval = max(MIN_INTERVAL_MINUTES, min(calculated_interval, MAX_INTERVAL_MINUTES))
        logger.debug(f"AdaptivePollingStrategy calculated interval: {final_interval} minutes for user {user_id}")
        return final_interval
