import math
from difflib import SequenceMatcher
from django.utils import timezone
from datetime import timedelta

# Critical keywords list for priority calculation
CRITICAL_WORDS = [
    "surgery", "accident", "emergency", "dying", "cancer",
    "icu", "blood", "flood", "homeless", "no food", "starving", "fire"
]

# Weights for matching algorithm
WEIGHTS = {
    'category': 0.35,
    'urgency': 0.25,
    'proximity': 0.25,
    'trust': 0.15
}

def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance in kilometers between two lat/lon points."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0.0
    
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def calculate_priority(title, description, category, urgency):
    """Calculate priority score and label for a help request."""
    score = 0.0
    
    # Urgency weight
    if urgency == 'high':
        score += 0.5
    elif urgency == 'medium':
        score += 0.25
    elif urgency == 'low':
        score += 0.0

    # Critical keywords check
    text = (title + " " + description).lower()
    for word in CRITICAL_WORDS:
        if word in text:
            score += 0.4
            break

    # Category check
    if category == 'Healthcare':
        score += 0.1

    # Cap score at 1.0
    score = min(score, 1.0)

    # Determine label
    if score >= 0.7:
        label = "Critical"
    elif score >= 0.4:
        label = "High"
    else:
        label = "Normal"

    return (score, label)

def check_duplicate(request):
    """Check if the request is a duplicate of the beneficiary's recent requests (last 30 days)."""
    # Use the time of the request itself (not "now"), and only look at EARLIER requests.
    # For a brand new request this is the same as before, but it also works for old data.
    request_time = request.created_at or timezone.now()
    thirty_days_before = request_time - timedelta(days=30)
    other_requests = request.__class__.objects.filter(
        beneficiary=request.beneficiary,
        created_at__gte=thirty_days_before,
        created_at__lte=request_time
    ).exclude(id=request.id)

    current_text = (request.title + " " + request.description).lower()

    for other in other_requests:
        if other.category == request.category:
            other_text = (other.title + " " + other.description).lower()
            similarity = SequenceMatcher(None, current_text, other_text).ratio()
            if similarity >= 0.8:
                return True
    return False

def check_suspicious(request):
    """Check if the beneficiary made more than 3 requests in the last 24 hours."""
    # Count the requests made in the 24 hours BEFORE this request (uses the request's own time)
    request_time = request.created_at or timezone.now()
    twenty_four_hours_before = request_time - timedelta(hours=24)
    recent_count = request.__class__.objects.filter(
        beneficiary=request.beneficiary,
        created_at__gte=twenty_four_hours_before,
        created_at__lte=request_time
    ).exclude(id=request.id).count()

    return recent_count >= 3

def match_score(request, ngo):
    """Calculate match score between a help request and an NGO."""
    # 1. Category similarity (Jaccard similarity)
    req_cat_set = {request.category.lower()}
    ngo_causes_set = {c.strip().lower() for c in ngo.causes.split(',') if c.strip()}
    
    if ngo_causes_set:
        intersection = len(req_cat_set.intersection(ngo_causes_set))
        union = len(req_cat_set.union(ngo_causes_set))
        cat_sim = intersection / union if union > 0 else 0.0
    else:
        cat_sim = 0.0

    # 2. Urgency score (request priority normalized 0-1)
    urg_score = request.priority if request.priority is not None else 0.0

    # 3. Proximity score
    distance = haversine_km(request.latitude, request.longitude, ngo.latitude, ngo.longitude)
    prox_score = 1.0 - min(distance / 300.0, 1.0)

    # 4. Trust score
    trust_score = (ngo.rating / 5.0) if ngo.rating else 0.0

    # Final weighted score
    total_score = (
        WEIGHTS['category'] * cat_sim +
        WEIGHTS['urgency'] * urg_score +
        WEIGHTS['proximity'] * prox_score +
        WEIGHTS['trust'] * trust_score
    )

    return round(total_score, 4)

def get_top_matches(request, how_many=3):
    """Return top matched verified NGOs for a request as a list of (ngo, score)."""
    from .models import NGOProfile
    verified_ngos = NGOProfile.objects.filter(is_verified=True)
    
    # Filter NGOs whose causes include the request category
    matching_ngos = []
    for ngo in verified_ngos:
        causes = [c.strip().lower() for c in ngo.causes.split(',') if c.strip()]
        if request.category.lower() in causes:
            matching_ngos.append(ngo)

    # If no NGO supports that category, fall back to all verified NGOs
    if not matching_ngos:
        matching_ngos = list(verified_ngos)

    scored_ngos = []
    for ngo in matching_ngos:
        score = match_score(request, ngo)
        scored_ngos.append((ngo, score))

    # Sort high to low by score
    scored_ngos.sort(key=lambda x: x[1], reverse=True)
    return scored_ngos[:how_many]
