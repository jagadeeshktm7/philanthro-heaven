import csv
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import HelpRequest, Match
from core.ai_engine import (calculate_priority, check_duplicate,
                            check_suspicious, get_top_matches)


class Command(BaseCommand):
    help = 'Run the AI engine again on the requests already in the database and rewrite dataset/system_output.csv (keeps your labels and truth columns).'

    def handle(self, *args, **options):
        dataset_dir = os.path.join(settings.BASE_DIR, 'dataset')
        out_path = os.path.join(dataset_dir, 'system_output.csv')

        # Read the old file only to keep the truth columns
        truth = {}
        if os.path.exists(out_path):
            with open(out_path, 'r', encoding='utf-8-sig', newline='') as f:
                for row in csv.DictReader(f):
                    truth[str(row['id']).strip()] = row

        rows = []
        # Oldest first, so the checks look only at earlier requests
        for req in HelpRequest.objects.order_by('created_at', 'id'):
            score, label = calculate_priority(req.title, req.description, req.category, req.urgency)
            req.priority = score
            req.priority_label = label
            req.is_duplicate = check_duplicate(req)
            req.is_suspicious = check_suspicious(req)
            req.save()

            # Make the Match rows again
            Match.objects.filter(request=req).delete()
            top = get_top_matches(req, how_many=3)
            for rank, (ngo, m_score) in enumerate(top, start=1):
                Match.objects.create(request=req, ngo=ngo, score=m_score, rank=rank)

            old = truth.get(str(req.id), {})
            rows.append({
                'id': req.id,
                'system_priority': label,
                'system_top_ngo': top[0][0].ngo_name if top else 'None',
                'system_is_duplicate': 1 if req.is_duplicate else 0,
                'system_is_suspicious': 1 if req.is_suspicious else 0,
                'is_duplicate_truth': old.get('is_duplicate_truth', ''),
                'is_suspicious_truth': old.get('is_suspicious_truth', ''),
            })

        rows.sort(key=lambda r: int(r['id']))
        fields = ['id', 'system_priority', 'system_top_ngo', 'system_is_duplicate',
                  'system_is_suspicious', 'is_duplicate_truth', 'is_suspicious_truth']
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f'Rescored {len(rows)} requests and rewrote {out_path}'))
