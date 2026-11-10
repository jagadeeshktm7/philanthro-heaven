from django.test import TestCase
from django.contrib.auth import get_user_model
from core.ai_engine import haversine_km, calculate_priority, check_duplicate, get_top_matches
from core.models import HelpRequest, NGOProfile
from core.cities import CITIES
from core.management.commands.evaluate_ai import calculate_binary_metrics, calculate_multiclass_metrics

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

    def test_evaluation_binary_metrics_helper(self):
        # Tiny example where answers can be checked by hand
        # y_true = [1, 1, 0, 0]
        # y_pred = [1, 0, 0, 1]
        # TP = 1, FN = 1, FP = 1, TN = 1
        y_true = [1, 1, 0, 0]
        y_pred = [1, 0, 0, 1]
        tp, fp, fn, tn, prec, rec, f1 = calculate_binary_metrics(y_true, y_pred)
        self.assertEqual(tp, 1)
        self.assertEqual(fp, 1)
        self.assertEqual(fn, 1)
        self.assertEqual(tn, 1)
        self.assertAlmostEqual(prec, 0.5)
        self.assertAlmostEqual(rec, 0.5)
        self.assertAlmostEqual(f1, 0.5)

    def test_evaluation_multiclass_metrics_helper(self):
        # Tiny 3-class example: classes = ['Critical', 'High', 'Normal']
        y_true = ['Critical', 'High', 'Normal', 'Critical']
        y_pred = ['Critical', 'Normal', 'Normal', 'High']
        acc, macro_f1, cm, class_metrics = calculate_multiclass_metrics(y_true, y_pred, ['Critical', 'High', 'Normal'])
        self.assertEqual(acc, 0.5) # 2 correct out of 4
        self.assertIn('Critical', class_metrics)
        self.assertIn('High', class_metrics)
        self.assertIn('Normal', class_metrics)
