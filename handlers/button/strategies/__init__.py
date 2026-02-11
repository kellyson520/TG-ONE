from .base import BaseMenuHandler
from .registry import MenuHandlerRegistry

# Import strategy modules to register them
from . import entry_point
from . import system
from . import rules
from . import dedup
from . import history
from . import settings
from . import copy
from . import ufb
from . import media
from . import ai
from . import search
from . import admin
from . import push
from . import analytics

__all__ = ["BaseMenuHandler", "MenuHandlerRegistry"]
