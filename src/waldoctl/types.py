"""Shared type aliases for robot control interfaces."""

from typing import Literal, Union

# Reference frame for Cartesian operations.
# WRF/TRF are built-in; custom frame names (str) are also accepted.
Frame = Union[Literal["WRF", "TRF"], str]

# Cartesian axis identifiers (unsigned — direction encoded in signed speed)
Axis = Literal["X", "Y", "Z", "RX", "RY", "RZ"]
