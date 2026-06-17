from typing import List, Tuple

Detection = Tuple[Tuple[int, int, int, int], float, int]

class_names = {0: 'duckie', 1: 'truck', 2: 'sign'}


def should_stop(detections: List[Detection], img_size: int) -> Tuple[bool, str]:
    if not detections:
        return False, ""
    for bbox, score, class_id in detections:


        x1, y1, x2, y2 = bbox

        box_height = y2 - y1
        box_width = x2 - x1
        box_area = box_width * box_height

        vertical_threshold = img_size * 0.45
        min_area_threshold = img_size * img_size * 0.08


        if y2 > img_size * 0.55:
            return True, f"Duckie close! Bottom edge at {y2}/{img_size}"

        if box_height > img_size * 0.3 and abs((x1 + x2) / 2 - img_size / 2) < img_size * 0.3:
            return True, f"Large duckie! Height: {box_height}/{img_size}"

        if y2 > vertical_threshold and box_area > min_area_threshold:
            return True, f"Duckie nearby! y2={y2}, area={box_area}"

    return False, ""