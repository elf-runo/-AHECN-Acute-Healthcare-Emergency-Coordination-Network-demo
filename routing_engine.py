# routing_engine.py
import math
from config import ASSUMED_AMBULANCE_SPEED_KMH

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def get_eta(src, dest):
    dist = haversine(*src, *dest)
    eta = (dist / ASSUMED_AMBULANCE_SPEED_KMH) * 60
    return round(eta,1)
