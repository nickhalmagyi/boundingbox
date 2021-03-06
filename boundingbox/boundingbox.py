import numpy as np
from math import degrees
from haversine import haversine
from importlib import reload
import time

import boundingbox.validations; reload(boundingbox.validations)
from boundingbox.validations.numbers import validate_positive_number
from boundingbox.validations.coordinates import validate_latlon_degrees, validate_latlons_degrees, validate_units


import boundingbox.coordinates; reload(boundingbox.coordinates)
from boundingbox.coordinates import convert_latlon_degrees_to_radians, mod_longitude_radians

from boundingbox.settings import EARTH_RADIUS, NORTH, SOUTH, EAST, WEST, KM, MILES, FRONT, REVERSE

class BoundingBox:
    def __init__(self, source, length, units=KM):
        self.source_degrees = source
        self.length = length
        self.units = units
        self.earth_radius = EARTH_RADIUS[units]
        self.source_radians = convert_latlon_degrees_to_radians(self.source_degrees)
        self.bbox = self.make_bounding_box(self.source_radians, self.length)


    @property
    def source_degrees(self):
        return self.__source_degrees

    @source_degrees.setter
    def source_degrees(self, source_degrees):
        validate_latlon_degrees(source_degrees)
        self.__source_degrees = source_degrees

    @property
    def length(self):
        return self.__length

    @length.setter
    def length(self, length):
        validate_positive_number(length)
        self.__length = length

    @property
    def units(self):
        return self.__units

    @units.setter
    def units(self, units):
        validate_units(units)
        self.__units = units
    
    
    def make_max_latitude_diff(self, length):
        return length / self.earth_radius


    def make_max_longitude_diff(self, source_radians, length):
        """
        :param source_radians: lat-lon pair in radians
        :param length: positive number
        :return: the maximum longitude difference between the source and a circle of radius=length around it.
        """
        d = length / self.earth_radius
        max_longitude_arg = np.cos(source_radians[0]) ** (-1) * \
                            (np.cos(d) ** 2 - np.sin(source_radians[0]) ** 2) ** (1 / 2)
        return np.abs(np.arccos(max_longitude_arg))


    def make_bounding_box(self, source_radians, length):
        """
        :param source_radians: lat-lon pair in radians
        :param length: positive number
        :return: dict with keys = [FRONT, REVERSE], 
        values are dicts with keys = [north, south, east, west] 
        and values in degrees
        """        
        bbox = {}
        bbox_front = {}
        bbox_reverse = {}

        max_latitude_diff = self.make_max_latitude_diff(length)

        # the bounding box does not reach either pole
        if (np.abs(source_radians[0]) + max_latitude_diff) <= np.pi / 2:
            max_longitude_diff = self.make_max_longitude_diff(source_radians, length)
            bbox_front[NORTH] = source_radians[0] + max_latitude_diff
            bbox_front[SOUTH] = source_radians[0] - max_latitude_diff
            bbox_front[EAST] = mod_longitude_radians(source_radians[1] + max_longitude_diff)
            bbox_front[WEST] = mod_longitude_radians(source_radians[1] - max_longitude_diff)

        # the bounding box surpasses at least one pole
        else:
            bbox_front[EAST] = np.pi / 2
            bbox_front[WEST] = -np.pi / 2
            bbox_reverse[EAST] = -np.pi / 2
            bbox_reverse[WEST] = np.pi / 2

            # the bounding box surpasses both north and south poles
            if (source_radians[0] + max_latitude_diff > np.pi / 2 and \
                source_radians[0] - max_latitude_diff < -np.pi / 2):
                bbox_front[NORTH] = np.pi / 2
                bbox_front[SOUTH] = -np.pi / 2

            # the bounding box surpasses the north pole
            elif source_radians[0] + max_latitude_diff > np.pi / 2:
                bbox_front[NORTH] = np.pi / 2
                bbox_front[SOUTH] = source_radians[0] - max_latitude_diff
                bbox_reverse[NORTH] = np.pi / 2
                # bbox_reverse[SOUTH] is the point at which the circle intersects 
                # lon = source[1] +/-  pi/2 .
                bbox_reverse[SOUTH] = np.arcsin(np.cos(length / self.earth_radius) / np.sin(source_radians[0]))

            # the bounding box surpasses the south pole
            elif source_radians[0] - max_latitude_diff < -np.pi / 2:
                bbox_front[NORTH] = source_radians[0] + max_latitude_diff
                bbox_front[SOUTH] = -np.pi / 2
                # bbox_reverse[NORTH] is the point at which the circle intersects 
                # lon = source[1] +/-  pi/2.
                bbox_reverse[NORTH] = np.arcsin(np.cos(length / self.earth_radius) / np.sin(source_radians[0]))
                bbox_reverse[SOUTH] = -np.pi / 2
            
            bbox_reverse = {k: degrees(v) for k, v in bbox_reverse.items()}
            bbox[REVERSE] = bbox_reverse
        

        # convert both bbox to degrees
        bbox_front = {k: degrees(v) for k, v in bbox_front.items()}
        bbox[FRONT] = bbox_front
        
        return bbox

    def target_in_bounding_box_front(self, target, bbox):
        return (target[0] >= bbox[SOUTH]) & (target[0] <= bbox[NORTH]) & (target[1] >= bbox[WEST]) & (target[1] <= bbox[EAST])

    def target_in_bounding_box_reverse(self, target, bbox):
        return 1 == (target[0] >= bbox[SOUTH]) & (target[0] <= bbox[NORTH]) & ~((target[1] >= bbox[EAST]) & (target[1] <= bbox[WEST]))


    def filter_targets_in_bbox(self, targets, bbox):
            """
            :param targets: An iterable of lat-lon pairs. 
            :param bbox: dict with keys = [north, south, east, west]
            :return: An iterable of lat-lon pairs where each pair is inside bbox
            """
            if bbox[WEST] <= bbox[EAST]:
                target_in_bounding_box = self.target_in_bounding_box_front
            else:
                target_in_bounding_box = self.target_in_bounding_box_reverse

            return targets[target_in_bounding_box(np.transpose(targets), bbox)]


    def filter_targets_in_bboxs(self, targets, bboxs):
        """
        :param bboxs: 
        :param targets: An iterable of lat-lon pairs. 
        :return: An iterable of lat-lon pairs where each pair is inside at least one of the bbox in bboxs
        """
        targets_filtered = []
        for k,v in bboxs.items():
            targets_filtered += list(self.filter_targets_in_bbox(targets, bboxs[k]))
        return targets_filtered


    def compute_distances_from_source(self, source_degrees, targets):
        """
        :param source_degrees: lat-lon pair in degrees
        :param targets: An iterable of lat-lon pairs. 
        :return: np array where each element is of the form [(lat, lon), distance]
        """
        if len(targets) == 0:
            return []
        targets_distance = np.array([[target, haversine(source_degrees, target)] for target in targets])
        # sort by haversine distance
        targets_dist_sorted = targets_distance[targets_distance[:,1].argsort()]
        return targets_dist_sorted


    def get_points_within_bbox(self, targets, bbox):
        """
        :param bbox: 
        :param targets: An iterable of lat-lon pairs. 
        :return: np array where each element is of the form [(lat, lon), distance] and is inside bbox
        """
        targets_filtered = self.filter_targets_in_bbox(targets, bbox)
        targets_dist = self.compute_distances_from_source(self.source_degrees, targets_filtered)
        return targets_dist


    def get_points_within_bboxs(self, targets, bboxs):
        """
        :param bboxs: dict where values are dicts with keys = [north, south, east, west]
        :param targets: An iterable of lat-lon pairs. 
        :return: all locations in targets which are inside ANY of the bbox in bboxs
        """
        targets_dist = []
        
        for k,v in bboxs.items():
            targets_dist += list(self.get_points_within_bbox(targets, bboxs[k]))
        return np.array(targets_dist)
