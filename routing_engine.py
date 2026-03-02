# routing_engine.py
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
    km = haversine_km(origin, dest)
    speed_kmh = speed_kmh if speed_kmh > 0 else 40.0
    return max(1.0, (km / speed_kmh) * 60.0)
