# synthetic_data.py
import random

def generate_case():
    categories = ["Maternal","Trauma","Stroke","Cardiac","Sepsis"]
    bundle = random.choice(categories)

    vitals = {
        "hr": random.randint(60,150),
        "rr": random.randint(12,35),
        "sbp": random.randint(80,160),
        "spo2": random.randint(85,100)
    }

    return bundle, vitals
