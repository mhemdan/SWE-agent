"""
Tool Error Detector Hook for SWE-Agent

Detects when the agent is stuck in a tool error retry loop and forces
alternative approaches or submission.

Prevents infinite loops caused by:
- Repeated tool failures (e.g., str_replace_editor whitespace mismatches)
- Same command failing multiple times with slight variations
- Agent not recognizing need to try different approach
"""
import logging
from collections import defaultdict
from typing import Any

from sweagent.agent.hooks.abstract import AbstractAgentHook
from sweagent.types import StepOutput

logger = logging.getLogger(__name__)


class ToolErrorDetectorHook(AbstractAgentHook):
    """
    Detects repeated tool errors and prevents infinite retry loops.

    Tracks:
    - Same tool failing multiple times in a row
    - Same error message appearing repeatedly
    - Total error count exceeding threshold

    Actions:
    - After N consecutive failures of same tool: suggests alternative
    - After M total errors in session: forces submission
    """

    def __init__(
        self,
        enabled: bool = True,
        max_consecutive_tool_errors: int = 5,
        max_total_errors: int = 15,
        max_same_error_message: int = 10,
        force_submit_on_max_errors: bool = True,
    ):
        """
        Initialize tool error detector.

        Args:
            enabled: Whether the hook is active
            max_consecutive_tool_errors: Max consecutive failures of same tool before intervention
            max_total_errors: Max total errors in session before forcing submission
            max_same_error_message: Max times same error message can appear before forcing submission
            force_submit_on_max_errors: Whether to force submit when thresholds are exceeded
        """
        self.enabled = enabled
        self.max_consecutive_tool_errors = max_consecutive_tool_errors
        self.max_total_errors = max_total_errors
        self.max_same_error_message = max_same_error_message
        self.force_submit_on_max_errors = force_submit_on_max_errors

        # Tracking state
        self._consecutive_errors = defaultdict(int)  # tool_name -> count
        self._total_errors = 0
        self._error_messages = defaultdict(int)  # error_msg -> count
        self._last_tool = None
        self._last_error = None
        self._intervention_count = 0
        self._forced_submit = False

    def on_actions_generated(self, *, step: StepOutput):
        """
        Intercept generated actions and force submit if error threshold exceeded.

        This is called after the model generates an action but before it's executed.
        If we've flagged that submission should be forced, we override the action.

        Args:
            step: The step output containing the generated action
        """
        if not self.enabled or not self.force_submit_on_max_errors:
            return

        if self._forced_submit and step.action != "submit":
            logger.error(
                f"ToolErrorDetectorHook: Forcing submit due to excessive errors. "
                f"Overriding action: {step.action}"
            )

            # Force the action to be submit
            original_action = step.action
            step.action = "submit"

            # Update thought to explain what happened
            if step.thought:
                step.thought = (
                    f"{step.thought.rstrip()}\n\n"
                    f"[ToolErrorDetectorHook: Excessive errors detected. "
                    f"Forcing submission instead of: {original_action}]"
                )
            else:
                step.thought = (
                    f"[ToolErrorDetectorHook: Excessive errors detected. "
                    f"Forcing submission to prevent infinite loop]"
                )

    def on_step_done(self, *, step: StepOutput, info=None):
        """
        Analyze step results and detect error patterns.

        Called after each step completes with observation.

        Args:
            step: The completed step output
            info: Additional agent info (optional, not used)
        """
        if not self.enabled:
            return

        observation = step.observation or ""
        action = step.action or ""

        # Detect if this step resulted in an error
        is_error = self._is_error_observation(observation)

        if is_error:
            self._handle_error(action, observation, step)
        else:
            # Success - reset consecutive error counter for this tool
            tool_name = self._extract_tool_name(action)
            if tool_name in self._consecutive_errors:
                logger.debug(f"ToolErrorDetectorHook: {tool_name} succeeded, resetting consecutive counter")
                self._consecutive_errors[tool_name] = 0

    def _is_error_observation(self, observation: str) -> bool:
        """Check if observation indicates a tool error."""
        observation_lower = observation.lower()

        error_indicators = [
            "error:",
            "failed:",
            "no replacement was performed",
            "could not find",
            "does not exist",
            "permission denied",
            "command not found",
            "syntax error",
            "invalid",
            "exception:",
            "traceback",
        ]

        return any(indicator in observation_lower for indicator in error_indicators)

    def _extract_tool_name(self, action: str) -> str:
        """Extract tool name from action string."""
        if not action:
            return "unknown"

        # Handle common tool patterns
        parts = action.strip().split()
        if not parts:
            return "unknown"

        tool = parts[0]

        # Normalize tool names
        if "str_replace" in tool:
            return "str_replace_editor"
        elif "edit" in tool:
            return "edit_file"
        elif "create" in tool:
            return "create_file"

        return tool

    def _handle_error(self, action: str, observation: str, step: StepOutput):
        """Handle detected error and check for intervention triggers."""
        tool_name = self._extract_tool_name(action)

        # Track consecutive errors for this tool
        self._consecutive_errors[tool_name] += 1
        self._total_errors += 1

        # Track specific error message
        error_key = self._extract_error_key(observation)
        self._error_messages[error_key] += 1

        logger.debug(
            f"ToolErrorDetectorHook: {tool_name} error #{self._consecutive_errors[tool_name]} "
            f"(total: {self._total_errors})"
        )

        # Check intervention thresholds
        consecutive = self._consecutive_errors[tool_name]
        same_error_count = self._error_messages[error_key]

        if consecutive >= self.max_consecutive_tool_errors:
            self._intervene_consecutive_errors(tool_name, consecutive, step)
        elif same_error_count >= self.max_same_error_message:
            self._intervene_same_error(error_key, same_error_count, step)
        elif self._total_errors >= self.max_total_errors:
            self._intervene_total_errors(step)

    def _extract_error_key(self, observation: str) -> str:
        """Extract key identifying this error type (first 100 chars of error message)."""
        # Find the actual error message
        lines = observation.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ['error', 'failed', 'exception', 'no replacement']):
                return line[:100]

        return observation[:100]

    def _intervene_consecutive_errors(self, tool_name: str, count: int, step: StepOutput):
        """Intervene when same tool fails repeatedly."""
        self._intervention_count += 1

        logger.warning(
            f"ToolErrorDetectorHook: {tool_name} failed {count} times consecutively. "
            f"Suggesting alternative approach."
        )

        # Modify observation to suggest alternative
        suggestion = self._get_alternative_suggestion(tool_name)

        step.observation = (
            f"{step.observation}\n\n"
            f"⚠️ SYSTEM INTERVENTION: {tool_name} has failed {count} times in a row.\n"
            f"{suggestion}\n"
            f"If you cannot make progress, consider submitting what you have completed so far."
        )

        # Reset counter for this tool to allow a few more tries with new approach
        self._consecutive_errors[tool_name] = 0

    def _intervene_same_error(self, error_key: str, count: int, step: StepOutput):
        """Intervene when same error message appears repeatedly."""
        logger.warning(
            f"ToolErrorDetectorHook: Same error appeared {count} times: {error_key}"
        )

        # Force submit if same error appears way too many times
        if count >= self.max_same_error_message * 2 and self.force_submit_on_max_errors:
            logger.error(
                f"ToolErrorDetectorHook: Same error appeared {count} times. "
                f"Forcing submission to prevent infinite loop."
            )
            self._forced_submit = True

        step.observation = (
            f"{step.observation}\n\n"
            f"⚠️ SYSTEM INTERVENTION: This same error has occurred {count} times.\n"
            f"Trying the same approach repeatedly will not succeed.\n"
            f"Please try a completely different approach, or submit what you have completed so far."
        )

    def _intervene_total_errors(self, step: StepOutput):
        """Intervene when total errors exceed threshold - force submission."""
        logger.error(
            f"ToolErrorDetectorHook: Total errors ({self._total_errors}) exceeded threshold "
            f"({self.max_total_errors}). Forcing submission."
        )

        # Set flag to force submit on next action
        if self.force_submit_on_max_errors:
            self._forced_submit = True

        step.observation = (
            f"{step.observation}\n\n"
            f"⛔ SYSTEM INTERVENTION: Too many errors ({self._total_errors}) encountered in this session.\n"
            f"You must now submit your work. Use the `submit` command to save your progress.\n"
            f"Do not attempt any more file operations."
        )

    def _get_alternative_suggestion(self, tool_name: str) -> str:
        """Get suggestion for alternative approach based on failing tool."""
        suggestions = {
            "str_replace_editor": (
                "The str_replace_editor requires exact whitespace matching.\n"
                "Alternative approaches:\n"
                "1. Use `cat` to view the exact file content and formatting first\n"
                "2. Try `sed` or `awk` for simpler replacements\n"
                "3. Manually rewrite the entire section if replacements keep failing"
            ),
            "edit_file": (
                "File editing is failing repeatedly.\n"
                "Alternative approaches:\n"
                "1. Read the file first to verify its current state\n"
                "2. Check if the file path is correct\n"
                "3. Try creating a new file instead of editing"
            ),
            "create_file": (
                "File creation is failing.\n"
                "Alternative approaches:\n"
                "1. Verify the directory exists first\n"
                "2. Check file permissions\n"
                "3. Try a different file path"
            ),
        }

        return suggestions.get(
            tool_name,
            f"Tool '{tool_name}' is failing repeatedly. Try a different tool or approach."
        )

    def get_state(self) -> dict[str, Any]:
        """Return current state for debugging."""
        return {
            "enabled": self.enabled,
            "total_errors": self._total_errors,
            "consecutive_errors": dict(self._consecutive_errors),
            "intervention_count": self._intervention_count,
            "forced_submit": self._forced_submit,
            "thresholds": {
                "max_consecutive": self.max_consecutive_tool_errors,
                "max_total": self.max_total_errors,
                "max_same_error": self.max_same_error_message,
            },
        }
