from .base import BASE_CSS, BASE_JS
from .braitenberg import BRAITENBERG_TEMPLATE
from .object_detection import OBJECT_DETECTION_TEMPLATE
from .lane_servoing import LANE_SERVOING_TEMPLATE
from .introduction import INTRODUCTION_TEMPLATE
from .project import get_template as get_project_template

__all__ = [
    'BASE_CSS',
    'BASE_JS',
    'BRAITENBERG_TEMPLATE',
    'OBJECT_DETECTION_TEMPLATE',
    'LANE_SERVOING_TEMPLATE',
    'INTRODUCTION_TEMPLATE',
    'get_project_template',
]
