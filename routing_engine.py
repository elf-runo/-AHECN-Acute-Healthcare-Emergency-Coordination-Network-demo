"""
routing_engine.py
Demo-safe routing: uses straight-line Haversine distance to estimate ETA.

This avoids reliance on public OSRM during demos.
"""

from __future__ import annotations
from typing import Tuple
import math

def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlon/2)**2
    return 2*r*math.asin(math.sqrt(h))

def get_eta(origin: Tuple[float, float], dest: Tuple[float, float], speed_kmh: float = 40.0) -> float:
    """
    Returns ETA in minutes using haversine distance / assumed speed.
    """
    km = haversine_km(origin, dest)
    if speed_kmh <= 0:
        speed_kmh = 40.0
    minutes = (km / speed_kmh) * 60.0
    return max(1.0, minutes)
