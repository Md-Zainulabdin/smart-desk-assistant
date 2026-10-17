from enum import Enum


class ContextState(str, Enum):
    AVAILABLE = "AVAILABLE"
    IN_MEETING = "IN_MEETING"
    AWAY = "AWAY"
    PRESENT_UNKNOWN = "PRESENT_UNKNOWN"

class NotificationMode(str, Enum):
    SPEAK_AND_SHOW = "SPEAK_AND_SHOW"
    SHOW_SILENTLY = "SHOW_SILENTLY"
    DELAY = "DELAY"
    MOBILE_ONLY = "MOBILE_ONLY"
