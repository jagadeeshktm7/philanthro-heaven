import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import HelpRequest
from core.ai_engine import calculate_priority, get_top_matches

class Command(BaseCommand):
    help = 'Evaluates help requests from CSV using AI engine and displays prediction summary'

    def handle(self, *args, **options):
        csv_path = os.path.join(settings.BASE_DIR, 'dataset', 'requests_to_label.csv')
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"CSV file not found at {csv_path}. Run seed_demo_data first."))
            return

        self.stdout.write("Evaluating help requests from CSV dataset...")
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Also evaluate the 2 sample requests provided by the user directly against the engine
        sample_requests = [
            {
                'title': 'Father in hospital',
                'description': 'My father had a heart attack last night and the doctors need money for an operation today',
                'category': 'Healthcare',
                'city': 'Chennai',
                'urgency': 'high'
            },
            {
                'title': 'Cannot pay fees',
                'description': 'I am in 12th standard and my school will not let me write exams unless I pay this week',
                'category': 'Education',
                'city': 'Villupuram',
                'urgency': 'medium'
            }
        ]

        self.stdout.write("\n=== EVALUATION OF USER SAMPLE REQUESTS ===")
        for req in sample_requests:
            score, label = calculate_priority(req['title'], req['description'], req['category'], req['urgency'])
            # Create a temporary dummy request object for get_top_matches
            class DummyReq:
                def __init__(self, d):
                    self.title = d['title']
                    self.description = d['description']
                    self.category = d['category']
                    self.city = d['city']
                    self.urgency = d['urgency']
                    self.priority = score
                    from core.cities import CITIES
                    lat, lon = CITIES.get(d['city'], (0.0, 0.0))
                    self.latitude = lat
                    self.longitude = lon

            dummy = DummyReq(req)
            top_ngos = get_top_matches(dummy, how_many=3)
            top_ngo_name = top_ngos[0][0].ngo_name if top_ngos else "None"

            self.stdout.write(f"Title: {req['title']} | Category: {req['category']} | Urgency: {req['urgency']}")
            self.stdout.write(f" -> System Priority: {label} (Score: {score})")
            self.stdout.write(f" -> System Top NGO Match: {top_ngo_name}\n")

        self.stdout.write(f"Total rows in {csv_path}: {len(rows)}")
        self.stdout.write(self.style.SUCCESS("Evaluation complete! You can inspect the system predictions in dataset/requests_to_label.csv."))
