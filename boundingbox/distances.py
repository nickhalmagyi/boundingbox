from boundingbox.boundingbox import BoundingBox
from haversine import haversine
import numpy as np
import time
from importlib import reload

import boundingbox.validations; reload(boundingbox.validations)
from boundingbox.validations.numbers import validate_strictly_positive_integer
from boundingbox.validations.coordinates import validate_latlons_degrees


def get_points_within_distance(source, targets, length):
    """
    It is possible for a point to be within the bbox but further than length from source.
    Here we remove such points.
    :param source: lat-lon tuple
    :param targets: iterable of the form [(lat, lon), dist]
    :param length: positive number
    :return: list of targets whose distance to source is less than length.
    """
    validate_latlons_degrees(targets)

    boundingbox = BoundingBox(source, length)
    targets_in_bbox = boundingbox.get_points_within_bboxs(targets, boundingbox.bbox)
    targets_within_distance = []
    for target in targets_in_bbox:
        if target[1] <= length:
            targets_within_distance.append(target)
        else:
            return targets_within_distance
    return targets_within_distance


def closest_points_are_within_length(targets_distance, N, length):
    """
    :param targets_dist: iterable of the form [(lat, lon), dist]
    :param N: strictly positive integer
    :param length: positive number
    :return: boolean, whether the distance from source to the N-th point in targets_dist is leq to length
    """
    return targets_distance[:N][-1][1] <= length


def get_closest_points(source_degrees, targets, N, length=None, validate=False):
    if validate:
        # only validate if flagged, this will incur a significant time penalty. 
        validate_strictly_positive_integer(N)
        validate_latlons_degrees(targets)

    if N > len(targets):
        # should just return all targets with distance and sorted by distance
        N = len(targets)

    boundingbox = BoundingBox(source_degrees, length)
    targets_filtered = boundingbox.filter_targets_in_bboxs(targets, boundingbox.bbox)
    targets_distance = boundingbox.compute_distances_from_source(source_degrees, targets_filtered)

    # i = 0
    while (len(targets_distance) < N) or not closest_points_are_within_length(targets_distance, N, boundingbox.length):
        print('in while loop')
    # rescale 
        if len(targets_distance) < N:
            boundingbox.length *= 1.25
        else:
            # set length to be the distance from source to the N-th point. 
            Nth_point_distance = targets_distance[:N][-1][1]
            if Nth_point_distance <= boundingbox.length:
                boundingbox.length *= 1.25
            else:
                boundingbox.length = Nth_point_distance

        boundingbox.bbox = boundingbox.make_bounding_box(boundingbox.source_radians, boundingbox.length)
        targets_filtered = boundingbox.filter_targets_in_bboxs(targets, boundingbox.bbox)
        targets_distance = boundingbox.compute_distances_from_source(source_degrees, targets_filtered)
        
        # i += 1
        # if i == 4:
        #     break

    return targets_distance[:N]
