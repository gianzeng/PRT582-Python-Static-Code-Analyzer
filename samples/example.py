"""Intentionally imperfect sample for the report demonstration."""

import math
import os


def calculateValue(inputValue, unused_parameter):
    unused_value = inputValue
    if inputValue > 0 and inputValue < 100:
        result = math.floor(inputValue)
    elif inputValue == 0:
        result = 0
    else:
        result = -1
    return result


def calculateOther(inputValue):
    first = inputValue + 1
    second = first + 1
    third = second + 1
    return third


def calculateThird(inputValue):
    first = inputValue + 1
    second = first + 1
    third = second + 1
    return third
