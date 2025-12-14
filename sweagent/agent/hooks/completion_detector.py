"""
Hook to detect when agent signals completion without explicit submit command.

This hook intercepts actions and detects when the agent indicates it's done
through comments or specific phrases, then automatically converts these signals
to proper submit commands.

This is a non-invasive extension that doesn't modify core agent behavior.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sweagent.agent.hooks.abstract import AbstractAgentHook
from sweagent.types import StepOutput

if TYPE_CHECKING:
    from sweagent.agent.agents import DefaultAgent


class CompletionDetectorHook(AbstractAgentHook):
    """Detects completion signals and auto-converts to submit command.

    This hook monitors agent actions for signals that indicate task completion,
    such as comments containing phrases like "no further commands to execute".
    When detected, it automatically converts these signals to a proper submit command.

    This allows models that struggle with explicit submission to still properly
    complete tasks without infinite loops.

    Args:
        phrases: List of phrases that indicate completion (case-insensitive)
        enabled: Whether the hook is active
    """

    def __init__(
        self,
        phrases: list[str] | None = None,
        enabled: bool = True,
    ):
        """Initialize the completion detector hook.

        Args:
            phrases: Custom completion phrases. If None, uses default set.
            enabled: Whether to activate the hook.
        """
        self.enabled = enabled
        self.phrases = phrases or [
            "no further commands to execute",
            "no more commands to execute",
            "no additional commands",
            "interaction is complete",
            "task is complete",
            "implementation is complete",
            "work is done",
            "finished",
        ]
        # Convert to lowercase for case-insensitive matching
        self.phrases = [p.lower() for p in self.phrases]

        self._agent = None
        self._detections = 0

    def on_init(self, *, agent: DefaultAgent):
        """Store agent reference for logging."""
        self._agent = agent
        if hasattr(agent, "logger"):
            agent.logger.debug(
                f"CompletionDetectorHook initialized with {len(self.phrases)} phrases"
            )

    def on_actions_generated(self, *, step: StepOutput):
        """Intercept generated actions and detect completion signals.

        This is called after the model generates an action but before it's executed.
        We check if the action is a comment indicating completion, and if so,
        convert it to a submit command.

        Args:
            step: The step output containing the generated action
        """
        if not self.enabled:
            return

        if not step.action:
            return

        action = step.action

        # Check if action is a comment (starts with #)
        stripped = action.lstrip()
        if not stripped.startswith("#"):
            return

        # Extract comment text
        comment_text = stripped.lstrip("#").strip().lower()

        # Check if comment contains any completion phrase
        if any(phrase in comment_text for phrase in self.phrases):
            self._detections += 1

            # Log detection
            if self._agent and hasattr(self._agent, "logger"):
                self._agent.logger.info(
                    f"CompletionDetectorHook: Detected completion signal in comment: '{action.strip()}'"
                )
                self._agent.logger.info(
                    "CompletionDetectorHook: Converting to submit command"
                )

            # Convert to submit command
            step.action = "submit"

            # Update thought to explain what happened
            if step.thought:
                step.thought = (
                    f"{step.thought.rstrip()}\n\n"
                    f"[CompletionDetectorHook: Detected completion signal, "
                    f"auto-submitting instead of executing comment]"
                )
            else:
                step.thought = (
                    "[CompletionDetectorHook: Detected completion signal in action, "
                    "auto-submitting]"
                )

    def on_run_done(self, *, trajectory, info):
        """Log statistics at the end of run."""
        if self._agent and hasattr(self._agent, "logger") and self._detections > 0:
            self._agent.logger.info(
                f"CompletionDetectorHook: Detected and converted {self._detections} "
                f"completion signal(s) to submit commands"
            )
