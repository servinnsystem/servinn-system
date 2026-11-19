# jobs/location_engine.py
import math

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points on the Earth's surface
    using the Haversine formula. Returns distance in kilometers (km).
    """
    R = 6371.0  # Earth's radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c

    return round(distance, 2)


def filter_jobs_by_proximity(user_lat, user_lon, jobs_list, max_distance_km=50):
    """
    Filters and sorts a list of job postings based on maximum distance threshold (km)
    from the candidate's current coordinates.
    """
    nearby_jobs = []

    for job in jobs_list:
        job_lat = job.get('latitude')
        job_lon = job.get('longitude')

        if job_lat is not None and job_lon is not None:
            distance = calculate_haversine_distance(user_lat, user_lon, float(job_lat), float(job_lon))
            job['distance_km'] = distance

            if distance <= max_distance_km:
                nearby_jobs.append(job)
        else:
            # If coordinates are missing, keep in list but set distance as None
            job['distance_km'] = None
            nearby_jobs.append(job)

    # Sort nearest jobs first (placing unmeasured distance at the end)
    return sorted(nearby_jobs, key=lambda x: (x['distance_km'] is None, x['distance_km']))