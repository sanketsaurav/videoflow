from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import numpy as np
import cv2

from ...core.node import ProcessorNode
from ...utils.parsers import parse_label_map

class ImageAnnotator(ProcessorNode):
    def _annotate(self, im : np.array, annotations : any) -> np.array:
        raise NotImplemented('Subclass must implement this method')

    def process(self, im : np.array, annotations : any) -> np.array:
        '''
        Returns a copy of `im` visually annotated with the annotations defined in `annotations`
        '''
        to_annotate = np.array(im)
        return self._annotate(to_annotate, annotations)
        
class BoundingBoxAnnotator(ImageAnnotator):
    def __init__(self, class_labels_path, box_color = (255, 225, 0), box_thickness = 2, text_color = (255, 255, 255)):
        self._box_color = box_color
        self._text_color = text_color
        self._box_thickness = box_thickness
        self._index_label_d = parse_label_map(class_labels_path)

    def _annotate(self, im : np.array, boxes : np.array) -> np.array:
        '''
        Arguments:
        - im: np.array
        - annotations: np.array of shape (nb_boxes, 6)
          second dimension entries are [xmin, ymin, xmax, ymax, class_index, score]
        '''

        for i in range(len(boxes)):
            bbox = boxes[i]
            xmin, ymin, xmax, ymax = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            y_label = ymin - 15 if ymin - 15 > 15 else min(ymin + 15, ymax)
            klass_id = bbox[4]
            klass_text = self._index_label_d[klass_id]
            confidence = bbox[5]
            label = "{}: {:.2f}%".format(klass_text, confidence * 100)
            cv2.rectangle(im, (xmin, ymin), (xmax, ymax), self._box_color, self._box_thickness)
            cv2.putText(im, label, (xmin, y_label), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self._text_color, lineType = cv2.LINE_AA)
        return im
