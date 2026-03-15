from enum import Enum, auto
import asyncio
import logging

logger = logging.getLogger(__name__)


class LessonPhase(Enum):
    INTRO = auto()       # Aura greets, asks if ready
    PRACTICE = auto()    # Aura gives phrase → user attempts → feedback → repeat (3x)
    NEXT = auto()        # Aura moves to next phoneme/exercise automatically


class LessonStateMachine:
    """
    Drives the coaching loop:
      INTRO → PRACTICE (repeat 3 attempts per exercise) → NEXT → PRACTICE → ... → COMPLETE
    """

    def __init__(self, total_exercises: int = 6, reps_required: int = 2):
        self.phase = LessonPhase.INTRO
        self.current_exercise_index = 0
        self.successes_on_current = 0
        self.total_exercises = total_exercises
        self.reps_required = reps_required
        self.lesson_complete = False

        # Silence nudge
        self._nudge_task: asyncio.Task | None = None
        self._nudge_callback = None
        self.nudge_delay_seconds = 3.0

    @property
    def state_name(self) -> str:
        return self.phase.name

    def start_practice(self):
        """Transition from INTRO → PRACTICE on first exercise."""
        logger.info("State: INTRO → PRACTICE (exercise 0)")
        self.phase = LessonPhase.PRACTICE
        self.current_exercise_index = 0
        self.successes_on_current = 0

    def record_success(self) -> dict:
        """
        Record a successful repetition.
        Returns status dict:
          - advance: True if should move to next exercise (reached required reps)
          - complete: True if all exercises done
          - reps: current successful reps
        """
        self.successes_on_current += 1
        reps = self.successes_on_current

        if self.successes_on_current >= self.reps_required:
            return {"advance": True, "complete": False, "reps": reps}

        return {"advance": False, "complete": False, "reps": reps}

    def advance_exercise(self) -> dict:
        """
        Move to the next exercise. Returns status dict.
        """
        self.phase = LessonPhase.NEXT
        self.current_exercise_index += 1
        self.successes_on_current = 0

        if self.current_exercise_index >= self.total_exercises:
            self.lesson_complete = True
            logger.info(f"State: NEXT → COMPLETE (all {self.total_exercises} exercises done)")
            return {"complete": True, "exercise_index": self.current_exercise_index}

        logger.info(f"State: NEXT → PRACTICE (exercise {self.current_exercise_index})")
        self.phase = LessonPhase.PRACTICE
        return {"complete": False, "exercise_index": self.current_exercise_index}

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.name,
            "exercise_index": self.current_exercise_index,
            "successes": self.successes_on_current,
            "total_exercises": self.total_exercises,
            "lesson_complete": self.lesson_complete,
        }

    # ── Silence nudge timer ──────────────────────────────────────────

    def start_nudge_timer(self, callback):
        """Start a timer that fires `callback` after nudge_delay_seconds of silence."""
        self.cancel_nudge_timer()
        self._nudge_callback = callback
        self._nudge_task = asyncio.ensure_future(self._nudge_loop())

    def cancel_nudge_timer(self):
        if self._nudge_task and not self._nudge_task.done():
            self._nudge_task.cancel()
            self._nudge_task = None

    def reset_nudge_timer(self):
        """Reset the timer (user spoke, so restart the countdown)."""
        if self._nudge_callback:
            self.start_nudge_timer(self._nudge_callback)

    async def _nudge_loop(self):
        try:
            while True:
                await asyncio.sleep(self.nudge_delay_seconds)
                if self.phase == LessonPhase.PRACTICE and self._nudge_callback:
                    await self._nudge_callback()
        except asyncio.CancelledError:
            pass
