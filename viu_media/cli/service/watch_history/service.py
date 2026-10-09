import logging
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from ....core.config.model import AppConfig
from ....libs.media_api.base import BaseApiClient
from ....libs.media_api.params import UpdateUserMediaListEntryParams
from ....libs.media_api.types import MediaItem, UserMediaListStatus
from ....libs.player.types import PlayerResult
from ..registry import MediaRegistryService

if TYPE_CHECKING:
    from ..tracking import TrackingService

logger = logging.getLogger(__name__)


class WatchHistoryService:
    def __init__(
        self,
        config: AppConfig,
        media_registry: MediaRegistryService,
        media_api: Optional[BaseApiClient] = None,
        tracking: Optional["TrackingService"] = None,
    ):
        self.config = config
        self.media_registry = media_registry
        self.media_api = media_api
        self.tracking = tracking

    def track(self, media_item: MediaItem, player_result: PlayerResult):
        logger.info(
            f"Updating watch history for {media_item.title.english} ({media_item.id}) with Episode={player_result.episode}; Stop Time={player_result.stop_time}; Total Duration={player_result.total_time}"
        )
        finished = self._episode_finished(player_result)
        status = self._status_after_watching(
            media_item, player_result.episode, finished
        )
        self.media_registry.update_media_index_entry(
            media_id=media_item.id,
            watched=True,
            media_item=media_item,
            last_watch_position=player_result.stop_time,
            total_duration=player_result.total_time,
            progress=player_result.episode,
            status=status,
        )
        if not finished:
            return
        if media_item.user_status is None and self.tracking is not None:
            # Like curd, start tracking shows that are not on a list yet. This
            # never overwrites an entry the item simply did not carry.
            self.tracking.add_if_missing(media_item, UserMediaListStatus.WATCHING)
        self._sync_remote(media_item, status=status, progress=player_result.episode)

    def _episode_finished(self, player_result: PlayerResult) -> bool:
        if player_result.stop_time and player_result.total_time:
            from ....core.utils.converter import calculate_completion_percentage

            completion_percentage = calculate_completion_percentage(
                player_result.stop_time, player_result.total_time
            )
            if completion_percentage < self.config.stream.episode_complete_at:
                logger.info(
                    f"Not updating remote watch history since completion percentage ({completion_percentage} is not greater than episode complete at ({self.config.stream.episode_complete_at}))"
                )
                return False
        return True

    @staticmethod
    def _status_after_watching(
        media_item: MediaItem, episode: Optional[str], finished: bool
    ) -> Optional[UserMediaListStatus]:
        """The list status implied by watching ``episode``, or None to keep it."""
        current = media_item.user_status.status if media_item.user_status else None
        watched = _as_int(episode)
        if (
            finished
            and media_item.episodes
            and watched is not None
            and watched >= media_item.episodes
        ):
            return UserMediaListStatus.COMPLETED
        if current == UserMediaListStatus.COMPLETED:
            return UserMediaListStatus.REPEATING
        if current in (
            UserMediaListStatus.PLANNING,
            UserMediaListStatus.PAUSED,
            UserMediaListStatus.DROPPED,
        ):
            return UserMediaListStatus.WATCHING
        return None

    def step_progress(
        self, media_item: MediaItem, delta: int
    ) -> Tuple[int, Optional[UserMediaListStatus], Dict[str, bool]]:
        """Moves progress by ``delta`` episodes and adjusts the status to match.

        Returns the new progress, the status that was set (or None) and the
        remote sync results.
        """
        entry = media_item.user_status
        current = (entry.progress if entry else None) or 0
        progress = max(0, current + delta)
        if media_item.episodes:
            progress = min(progress, media_item.episodes)
        current_status = entry.status if entry else None
        status: Optional[UserMediaListStatus] = None
        if media_item.episodes and progress == media_item.episodes and delta > 0:
            status = UserMediaListStatus.COMPLETED
        elif delta < 0 and current_status == UserMediaListStatus.COMPLETED:
            status = UserMediaListStatus.WATCHING
        elif progress > 0 and current_status in (
            None,
            UserMediaListStatus.PLANNING,
            UserMediaListStatus.PAUSED,
            UserMediaListStatus.DROPPED,
        ):
            status = UserMediaListStatus.WATCHING
        results = self.update(media_item, progress=str(progress), status=status)
        return progress, status, results

    def get_episode(self, media_item: MediaItem):
        index_entry = self.media_registry.get_media_index_entry(media_item.id)
        current_remote_episode = None
        current_local_episode = None
        start_time = None
        episode = None

        if media_item.user_status:
            # TODO: change mediaa item progress to a string
            current_remote_episode = str(media_item.user_status.progress)
        if index_entry:
            current_local_episode = index_entry.progress
            start_time = index_entry.last_watch_position
            total_duration = index_entry.total_duration
            if start_time and total_duration and current_local_episode:
                from ....core.utils.converter import calculate_completion_percentage

                if (
                    calculate_completion_percentage(start_time, total_duration)
                    >= self.config.stream.episode_complete_at
                ):
                    start_time = None
                    try:
                        current_local_episode = str(int(current_local_episode) + 1)
                    except Exception:
                        # incase its a float
                        pass
        else:
            current_local_episode = current_remote_episode
        if not media_item.user_status:
            current_remote_episode = current_local_episode
        if current_local_episode != current_remote_episode:
            if self.config.general.preferred_tracker == "local":
                episode = current_local_episode
            else:
                episode = current_remote_episode
        else:
            episode = current_local_episode

        # TODO: check if start time is mostly complete and increment the episode
        if episode == "0":
            episode = "1"
        return episode, start_time

    def update(
        self,
        media_item: MediaItem,
        progress: Optional[str] = None,
        status: Optional[UserMediaListStatus] = None,
        score: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, bool]:
        """Saves a change locally, then pushes it to the remote trackers.

        Returns the ``{tracker: succeeded}`` map of the remote sync.
        """
        self.media_registry.update_media_index_entry(
            media_id=media_item.id,
            media_item=media_item,
            progress=progress,
            status=status,
            score=score,
            notes=notes,
        )

        return self._sync_remote(
            media_item, status=status, progress=progress, score=score
        )

    def _sync_remote(
        self,
        media_item: MediaItem,
        status: Optional[UserMediaListStatus] = None,
        progress: Optional[str] = None,
        score: Optional[float] = None,
    ) -> Dict[str, bool]:
        """Pushes a change to the remote trackers; returns per-tracker results."""
        if self.tracking is not None:
            results = self.tracking.update(
                media_item, status=status, progress=progress, score=score
            )
            if not results:
                logger.info("No remote tracker is enabled and logged in")
            return results

        if not self.media_api or not self.media_api.is_authenticated():
            logger.warning("Not logged in")
            return {}
        succeeded = self.media_api.update_list_entry(
            UpdateUserMediaListEntryParams(
                media_id=media_item.id, status=status, score=score, progress=progress
            )
        )
        if succeeded:
            logger.info(f"Successfully updated remote progress to {progress}")
        else:
            logger.warning(f"Failed to update remote progress to {progress}")
        return {self.config.general.media_api: succeeded}

    def add_media_to_list_if_not_present(self, media_item: MediaItem):
        """Adds a media item to the user's PLANNING list if it's not already on any list."""
        if self.tracking is not None:
            added = self.tracking.add_if_missing(media_item)
            if added:
                self.media_registry.update_media_index_entry(
                    media_id=media_item.id,
                    media_item=media_item,
                    status=UserMediaListStatus.PLANNING,
                )
                logger.info(
                    f"Added '{media_item.title.english}' to 'Planning' on {', '.join(added)}."
                )
            return
        if not self.media_api or not self.media_api.is_authenticated():
            return

        # If user_status is None, it means the item is not on the user's list.
        if media_item.user_status is None:
            logger.info(
                f"'{media_item.title.english}' not on list. Adding to 'Planning'."
            )
            self.update(media_item, status=UserMediaListStatus.PLANNING)


def _as_int(value: Optional[str]) -> Optional[int]:
    try:
        return int(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
