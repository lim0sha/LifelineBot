from .advice import register_handlers as register_advice
from .anonymous import register_handlers as register_anonymous
from .common import register_handlers as register_common
from .meeting import register_handlers as register_meeting
from .menu import register_menu_handlers
from .profile import register_handlers as register_profile
from .start import register_handlers as register_start


def register_all_handlers(dp):
    register_menu_handlers(dp)
    register_anonymous(dp)
    register_meeting(dp)
    register_advice(dp)
    register_profile(dp)
    register_start(dp)
    register_common(dp)
