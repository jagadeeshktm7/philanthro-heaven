from django.test import TestCase
from django.contrib.auth import get_user_model
from core.ai_engine import haversine_km, calculate_priority, check_duplicate, get_top_matches
from core.models import HelpRequest, NGOProfile
from core.cities import CITIES

User = get_user_model()

class AIEngineTestCase(TestCase):
    def setUp(self):
        # Create a test beneficiary user
        self.beneficiary = User.objects.create_user(
            username='testbeneficiary',
            password='password123',
            role='beneficiary',
            city='Chennai'
        )

    def test_haversine_km(self):
        # Chennai coordinates (13.0827, 80.2707) to Bangalore coordinates (12.9716, 77.5946)
        # Expected distance is roughly ~290 km
        lat1, lon1 = CITIES['Chennai']
        lat2, lon2 = CITIES['Bangalore']
        distance = haversine_km(lat1, lon1, lat2, lon2)
        self.assertTrue(280 <= distance <= 300, f"Distance {distance} is not around 290 km")

    def test_calculate_priority(self):
        # A surgery request with urgency high should be Critical (score >= 0.7)
        score, label = calculate_priority("Urgent surgery needed", "Patient needs emergency surgery immediately.", "Healthcare", "high")
        self.assertEqual(label, "Critical")
        self.assertGreaterEqual(score, 0.7)

    def test_check_duplicate(self):
        # Create first request
        req1 = HelpRequest.objects.create(
            beneficiary=self.beneficiary,
            title="Need food supplies",
            category="Food",
            description="Our family has no food for today.",
            city="Chennai",
            urgency="medium"
        )

        # Create identical second request
        req2 = HelpRequest.objects.create(
            beneficiary=self.beneficiary,
            title="Need food supplies",
            category="Food",
            description="Our family has no food for today.",
            city="Chennai",
            urgency="medium"
        )

        is_dup = check_duplicate(req2)
        self.assertTrue(is_dup)

    def test_get_top_matches_category_filtering(self):
        # Create an Education NGO
        edu_user = User.objects.create_user(username='edungo', password='password123', role='ngo', city='Chennai')
        edu_ngo = NGOProfile.objects.create(
            user=edu_user,
            ngo_name='Education Trust',
            registration_number='REG-EDU',
            causes='Education',
            city='Chennai',
            is_verified=True,
            rating=5.0
        )

        # Create a Healthcare NGO
        health_user = User.objects.create_user(username='healthngo', password='password123', role='ngo', city='Chennai')
        health_ngo = NGOProfile.objects.create(
            user=health_user,
            ngo_name='Health Care Foundation',
            registration_number='REG-HLT',
            causes='Healthcare',
            city='Chennai',
            is_verified=True,
            rating=3.0
        )

        # Create a Healthcare request
        health_req = HelpRequest.objects.create(
            beneficiary=self.beneficiary,
            title='Medical treatment needed',
            category='Healthcare',
            description='Patient needs urgent medicine and care.',
            city='Chennai',
            urgency='high'
        )

        top_matches = get_top_matches(health_req, how_many=3)
        top_ngo_ids = [ngo.id for ngo, score in top_matches]

        # The Health NGO must be in top matches, and Education NGO must not be in top matches
        self.assertIn(health_ngo.id, top_ngo_ids)
        self.assertNotIn(edu_ngo.id, top_ngo_ids)
