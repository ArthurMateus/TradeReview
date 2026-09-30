"""
Persistent Kill Switch (Invariant A4).
Halts all order submissions immediately upon activation via CLI or Telegram /kill.
State persists across application restarts in a local statefile.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

KILL_STATE_FILE = Path(".kill_switch_active.json")


class KillSwitch:
    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or KILL_STATE_FILE

    def is_active(self) -> bool:
        """Returns True if the kill switch is currently active (trading halted)."""
        if not self.state_file.exists():
            return False
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("active", False))
        except Exception as e:
            logger.error(f"Error reading kill switch state: {e}. Defaulting to FAIL-CLOSED (active=True).")
            return True  # Fail-closed (Invariant A2)

    def activate(self, reason: str = "Manual kill switch triggered"):
        """Activates the kill switch, halting all order executions immediately."""
        data = {
            "active": True,
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.warning(f"🚨 KILL SWITCH ACTIVATED: {reason}")

    def deactivate(self):
        """Resets the kill switch allowing trading to resume."""
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("🟢 Kill switch deactivated. Normal trading resumed.")


kill_switch = KillSwitch()
