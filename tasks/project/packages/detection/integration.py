from typing import Tuple
# reusing the same code as in the tasks
MODEL_PATH = "tasks/object_detection/models/best.onnx"



def NUMBER_FRAMES_SKIPPED() -> int:

    return 2


def filter_by_classes(pred_class: int) -> bool:
    # for now the bot will still only stop for duckies
    # if one wishes to change it it has to be done in stop_logic.py
    return True


def filter_by_scores(score: float) -> bool:

    return score >= 0.6


def filter_by_bboxes(bbox: Tuple[int, int, int, int]) -> bool:

    xmin, ymin, xmax, ymax = bbox
    width = xmax - xmin
    height = ymax - ymin
    area = width * height
    return area > 800