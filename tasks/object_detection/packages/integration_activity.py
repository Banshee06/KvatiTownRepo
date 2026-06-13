from typing import Tuple

MODEL_PATH = "tasks/object_detection/models/best.onnx"



def NUMBER_FRAMES_SKIPPED() -> int:

    return 2


def filter_by_classes(pred_class: int) -> bool:
    "for now the bot will detect any obstacle in the class "
    "later can be changed here and in the stop_activity.py file stop function"
    return True


def filter_by_scores(score: float) -> bool:

    return score >= 0.6


def filter_by_bboxes(bbox: Tuple[int, int, int, int]) -> bool:

    xmin, ymin, xmax, ymax = bbox
    width = xmax - xmin
    height = ymax - ymin
    area = width * height
    return area > 800