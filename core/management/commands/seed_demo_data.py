import random
import csv
import os
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from core.models import NGOProfile, HelpRequest, Match
from core.cities import CITIES, CATEGORIES
from core.ai_engine import calculate_priority, check_duplicate, check_suspicious, get_top_matches

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds highly varied demo data, realistic priorities, and exports separate to_label, system_output, and ngo_list CSVs.'

    def handle(self, *args, **options):
        # Set random seed for reproducibility
        random.seed(42)

        self.stdout.write("Deleting old demo data and old CSV datasets...")
        Match.objects.all().delete()
        HelpRequest.objects.all().delete()
        NGOProfile.objects.all().delete()
        User.objects.filter(username__startswith='demo_').delete()

        dataset_dir = os.path.join(settings.BASE_DIR, 'dataset')
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Remove old requests_to_label.csv if present
        old_csv = os.path.join(dataset_dir, 'requests_to_label.csv')
        if os.path.exists(old_csv):
            os.remove(old_csv)

        self.stdout.write("Creating 20 verified NGOs...")
        city_names = list(CITIES.keys())
        category_names = [cat[0] for cat in CATEGORIES]
        
        ngo_profiles = []
        for i in range(1, 21):
            username = f'demo_ngo_{i}'
            email = f'{username}@example.com'
            user = User.objects.create_user(username=username, email=email, password='password123', role='ngo')
            
            city = city_names[(i - 1) % len(city_names)]
            num_causes = random.randint(1, 3)
            chosen_causes = random.sample(category_names, num_causes)
            causes_str = ','.join(chosen_causes)
            rating = round(random.uniform(2.5, 5.0), 1)

            ngo_profile = NGOProfile.objects.create(
                user=user,
                ngo_name=f'NGO Organization {i}',
                registration_number=f'REG-2026-{i:03d}',
                description=f'Dedicated charity working in {city} for {causes_str}.',
                causes=causes_str,
                city=city,
                is_verified=True,
                rating=rating
            )
            ngo_profiles.append(ngo_profile)

        self.stdout.write("Creating 30 beneficiary users...")
        beneficiaries = []
        for i in range(1, 31):
            username = f'demo_beneficiary_{i}'
            email = f'{username}@example.com'
            user = User.objects.create_user(username=username, email=email, password='password123', role='beneficiary')
            beneficiaries.append(user)

        self.stdout.write("Preparing 100 base help requests with 8+ varied templates per category...")

        # At least 8 distinct templates per category with placeholders
        templates = {
            'Education': [
                ("Tuition fees support for {name}", "My child {name} studies in grade {grade} at {city} school. We are unable to pay {amount} rupees tuition fee due this month.", "medium", False),
                ("School books for {name}", "Student {name} needs notebooks and stationery items for standard {grade}. Family income is very low in {city}.", "low", False),
                ("Exam fee payment assistance", "School management threatened to bar {name} (grade {grade}) from semester exams unless {amount} fee is cleared in {city}.", "high", False),
                ("Uniform and shoes aid", "Required school uniform and shoes for {name}, studying in 8th grade at {city} municipal school.", "low", False),
                ("Orphan student tuition support", "Guardian of {name} passed away; seeking financial aid of {amount} for {city} college education fees.", "high", False),
                ("Laptop request for online classes", "{name} in grade {grade} requires a basic laptop to attend online learning modules in {city}.", "medium", False),
                ("Board exam coaching fees", "Financial hardship in {city} preventing {name} from paying {amount} coaching fees for 12th board exams.", "high", False),
                ("Library and lab fee aid", "Student {name} in {city} needs {amount} for science lab deposit and library subscription.", "low", False),
            ],
            'Food': [
                ("Daily meals for family of {count}", "Our family of {count} members in {city} has been surviving on single meals for {days} days due to unemployment.", "medium", False),
                ("Severe starvation emergency", "Elderly residents in {city} slum are starving with absolutely no food supplies left for {days} days.", "high", True), # Critical
                ("Grocery ration kit request", "Requesting monthly grocery provisions (rice, lentils, cooking oil) for household of {count} in {city}.", "low", False),
                ("Milk and nutrition for infants", "Single mother in {city} cannot afford baby milk and nutritional supplements for {days} days.", "medium", False),
                ("Community kitchen food aid", "Migrant laborer family of {count} stranded in {city} without kitchen rations for {days} days.", "medium", False),
                ("Emergency food supply", "No food available at home in {city} for {count} persons since {days} days ago.", "high", False),
                ("Dry ration support", "Local flood in {city} spoiled our pantry; seeking basic food rations for {count} people.", "medium", False),
                ("Nutritional support for children", "Orphanage caretaker in {city} needs food supplies to feed {count} children this month.", "medium", False),
            ],
            'Healthcare': [
                ("Emergency surgery funds for {name}", "{name} met with a terrible accident in {city} and doctors scheduled emergency surgery today in ICU.", "high", True), # Critical
                ("Cancer treatment medicine for {name}", "Unable to afford monthly chemotherapy medicines costing {amount} for {name} battling cancer in {city}.", "high", True), # Critical
                ("Diabetes medication for senior", "Elderly father in {city} requires insulin and regular diabetes medicines costing {amount}.", "medium", False),
                ("Heart attack operation aid", "{name} suffered a severe heart attack in {city}; immediate surgery deposit of {amount} required.", "high", True), # Critical
                ("Post-surgery recovery care", "Patient {name} discharged from {city} hospital needs special nutritional care and medicines.", "medium", False),
                ("Kidney dialysis support", "Weekly dialysis sessions cost {amount} for {name} in {city} hospital; seeking financial aid.", "high", False),
                ("Emergency blood transfusion", "Patient {name} in {city} hospital needs urgent blood transfusion and ICU care.", "high", True), # Critical
                ("Dental surgery financial aid", "Severe tooth infection requiring minor surgery costing {amount} for {name} in {city}.", "low", False),
            ],
            'Shelter': [
                ("Roof repair after storm", "Heavy storm in {city} destroyed tin roof of our house; {amount} needed for roof restoration.", "medium", False),
                ("Homeless after devastating fire", "Accidental fire in {city} burnt down our dwelling; family of {count} is currently homeless.", "high", True), # Critical
                ("House rent arrears assistance", "Landlord threatening eviction in {city} within {days} days unless past rent of {amount} is cleared.", "high", False),
                ("Temporary shelter for migrants", "Displaced family of {count} in {city} sleeping on streets for {days} days seeking shelter aid.", "medium", False),
                ("Wall collapse repair", "Monsoon rains caused bedroom wall collapse in {city} house; {amount} required to rebuild.", "medium", False),
                ("Widow housing assistance", "Widowed mother with {count} children in {city} needs help repairing leaking roof before monsoon.", "medium", False),
                ("Shelter deposit support", "Need {amount} advance deposit to secure safe rental room in {city} after displacement.", "low", False),
                ("Emergency flood shelter aid", "River overflow flooded our {city} settlement; family of {count} displaced for {days} days.", "high", True), # Critical
            ],
            'Skill Development': [
                ("Vocational computer course fee", "Unemployed youth {name} in {city} wants to enroll in {amount} digital skills training program.", "low", False),
                ("Tailoring machine for livelihood", "Widow in {city} requesting a sewing machine worth {amount} to earn independent income.", "medium", False),
                ("Automotive mechanic training", "{name} seeking sponsorship of {amount} for technical apprenticeship at {city} auto workshop.", "medium", False),
                ("Mobile repair training course", "Young graduate in {city} needs {amount} course fee for cell phone hardware repair training.", "low", False),
                ("Handicraft toolkit assistance", "Artisan family in {city} needs raw materials and tools worth {amount} to restart craft work.", "medium", False),
                ("Electrician course sponsorship", "{name} in {city} looking for financial help to complete certified electrician diploma.", "low", False),
                ("Typing and data entry class", "Job seeker {name} in {city} needs {amount} for clerical skill certification exam.", "low", False),
                ("Welding trade training aid", "Unemployed person in {city} seeking {amount} for industrial welding certificate training.", "medium", False),
            ],
            'Other': [
                ("Wheelchair for disabled member", "{name} in {city} is physically disabled and needs an orthopedic wheelchair costing {amount}.", "medium", False),
                ("Prescription eyeglasses for elder", "Grandmother in {city} has poor eyesight and requires customized eyeglasses costing {amount}.", "low", False),
                ("Emergency debt relief", "Harassed by local lenders in {city} for {amount} emergency medical loan taken last month.", "medium", False),
                ("Artificial limb support", "{name} lost leg in {city} accident; needs prosthetic limb costing {amount} to walk again.", "high", False),
                ("Hearing aid device assistance", "Hearing impaired child {name} in {city} needs digital hearing aid device worth {amount}.", "medium", False),
                ("Cremation and funeral expenses", "Lost sole breadwinner in {city}; family needs {amount} for final funeral rites.", "high", False),
                ("Blanket and warm clothing drive", "Homeless elderly individuals in {city} shivering in winter without blankets.", "low", False),
                ("Emergency travel fare", "Need {amount} train travel fare to return to native village in {city} after job failure.", "low", False),
            ]
        }

        names = ["Ramesh", "Priya", "Karthik", "Anitha", "Surya", "Divya", "Vijay", "Meena", "Kumar", "Selvi", "Arun", "Deepa"]
        grades = ["6th", "8th", "9th", "10th", "11th", "12th"]
        amounts = ["2,500", "5,000", "7,500", "10,000", "15,000", "20,000"]
        counts = [3, 4, 5, 6]
        day_counts = [2, 3, 5, 7, 10]

        raw_requests_meta = []
        now = timezone.now()

        # Distribution targets: ~10 Critical, ~25 High, ~65 Normal
        # Let's craft 10 critical requests specifically
        critical_count = 0
        target_critical = 10
        target_high = 25
        target_normal = 65

        # We will generate 100 base requests total
        generated_count = 0
        
        # Keep track of generated texts to ensure high distinctness
        generated_texts = set()

        while generated_count < 100:
            category = random.choice(category_names)
            template_list = templates[category]
            
            # If we need critical ones, pick templates marked critical or inject critical words
            if critical_count < target_critical:
                crit_templates = [t for t in template_list if t[3] == True]
                if crit_templates and random.random() < 0.8:
                    title_tmpl, desc_tmpl_raw, urgency, is_crit = random.choice(crit_templates)
                else:
                    title_tmpl, desc_tmpl_raw, urgency, is_crit = random.choice(template_list)
                    # Force critical injection
                    cw = random.choice(["surgery", "accident", "icu", "dying", "cancer", "flood", "starving"])
                    desc_tmpl_raw = f"Critical emergency involving {cw}. " + desc_tmpl_raw
                    is_crit = True
            else:
                non_crit_templates = [t for t in template_list if t[3] == False]
                title_tmpl, desc_tmpl_raw, urgency, is_crit = random.choice(non_crit_templates if non_crit_templates else template_list)
                is_crit = False

            beneficiary = random.choice(beneficiaries)
            city = random.choice(city_names)
            name = random.choice(names)
            grade = random.choice(grades)
            amount = random.choice(amounts)
            count = random.choice(counts)
            days = random.choice(day_counts)

            title = title_tmpl.format(name=name, grade=grade, amount=amount, count=count, days=days, city=city)
            description = desc_tmpl_raw.format(name=name, grade=grade, amount=amount, count=count, days=days, city=city)

            # Ensure uniqueness
            text_signature = title + " | " + description
            if text_signature in generated_texts:
                continue
            generated_texts.add(text_signature)

            # Random created_at in the last 60 days
            days_ago = random.uniform(0, 60)
            req_date = now - timedelta(days=days_ago)

            if is_crit:
                critical_count += 1

            raw_requests_meta.append({
                'beneficiary': beneficiary,
                'title': title,
                'category': category,
                'description': description,
                'city': city,
                'urgency': urgency,
                'created_at': req_date,
                'is_duplicate_truth': 0,
                'is_suspicious_truth': 0,
                'is_hard_negative': 0
            })
            generated_count += 1

        # 3. Create 15 near-duplicates AND 10 hard negatives
        # Pick 15 random requests to make near-duplicates of
        near_dup_sources = random.sample(raw_requests_meta, 15)
        for src in near_dup_sources:
            later_date = src['created_at'] + timedelta(days=random.randint(1, 8))
            if later_date > now:
                later_date = now - timedelta(hours=random.randint(1, 12))

            # Near-duplicate: same category, slightly changed words
            new_title = src['title'] + " (Reminder)"
            new_desc = src['description'] + " Please review this urgent matter again."

            raw_requests_meta.append({
                'beneficiary': src['beneficiary'],
                'title': new_title,
                'category': src['category'],
                'description': new_desc,
                'city': src['city'],
                'urgency': src['urgency'],
                'created_at': later_date,
                'is_duplicate_truth': 1,
                'is_suspicious_truth': 0,
                'is_hard_negative': 0
            })

        # Pick 10 random requests to make hard negatives of (same user, same category, really different need)
        hard_neg_sources = random.sample(raw_requests_meta, 10)
        for src in hard_neg_sources:
            later_date = src['created_at'] + timedelta(days=random.randint(1, 8))
            if later_date > now:
                later_date = now - timedelta(hours=random.randint(1, 12))

            # Hard negative: same user and category, but completely different problem/description
            other_cat_templates = templates[src['category']]
            alt_t, alt_d, alt_u, _ = random.choice(other_cat_templates)
            new_title = "Different requirement: " + alt_t
            new_desc = "Additionally, we have another unrelated need: " + alt_d

            raw_requests_meta.append({
                'beneficiary': src['beneficiary'],
                'title': new_title,
                'category': src['category'],
                'description': new_desc,
                'city': src['city'],
                'urgency': alt_u,
                'created_at': later_date,
                'is_duplicate_truth': 0,
                'is_suspicious_truth': 0,
                'is_hard_negative': 1
            })

        # 4. Make 5 suspicious cases on purpose (one user sending 4 or more requests in one day)
        suspicious_users = random.sample(beneficiaries, 5)
        for s_user in suspicious_users:
            burst_day = now - timedelta(days=random.randint(2, 40))
            # 4 requests within a few hours on the same day
            for s_i in range(4):
                req_time = burst_day + timedelta(minutes=s_i * 20)
                is_susp_truth = 1 if s_i >= 2 else 0 # 3rd and 4th request marked suspicious
                cat = random.choice(category_names)
                
                raw_requests_meta.append({
                    'beneficiary': s_user,
                    'title': f"Rapid submission {s_i+1} for {cat}",
                    'category': cat,
                    'description': f"Submitting multiple requests quickly regarding {cat.lower()} support requirement number {s_i+1}.",
                    'city': random.choice(city_names),
                    'urgency': 'medium',
                    'created_at': req_time,
                    'is_duplicate_truth': 0,
                    'is_suspicious_truth': is_susp_truth,
                    'is_hard_negative': 0
                })

        # 4. Sort all requests by created_at ascending (oldest first) so duplicate & suspicious checks work correctly in chronological order
        raw_requests_meta.sort(key=lambda x: x['created_at'])

        self.stdout.write(f"Creating {len(raw_requests_meta)} help requests chronologically...")

        to_label_rows = []
        system_output_rows = []

        priority_counts = {'Critical': 0, 'High': 0, 'Normal': 0}
        duplicate_count = 0

        for meta in raw_requests_meta:
            help_req = HelpRequest.objects.create(
                beneficiary=meta['beneficiary'],
                title=meta['title'],
                category=meta['category'],
                description=meta['description'],
                city=meta['city'],
                urgency=meta['urgency']
            )

            # Set created_at with queryset .update() BEFORE running duplicate and suspicious checks
            HelpRequest.objects.filter(id=help_req.id).update(created_at=meta['created_at'])
            help_req.refresh_from_db()

            # Run AI Engine calculations
            score, label = calculate_priority(help_req.title, help_req.description, help_req.category, help_req.urgency)
            help_req.priority = score
            help_req.priority_label = label
            help_req.save()

            help_req.is_duplicate = check_duplicate(help_req)
            help_req.is_suspicious = check_suspicious(help_req)
            help_req.save()

            if help_req.is_duplicate:
                duplicate_count += 1

            if label in priority_counts:
                priority_counts[label] += 1

            top_ngos = get_top_matches(help_req, how_many=3)
            for rank, (ngo, m_score) in enumerate(top_ngos, start=1):
                Match.objects.create(
                    request=help_req,
                    ngo=ngo,
                    score=m_score,
                    rank=rank
                )

            top_ngo_name = top_ngos[0][0].ngo_name if top_ngos else "None"

            # 5. Build dataset files per instructions
            to_label_rows.append({
                'id': help_req.id,
                'title': help_req.title,
                'description': help_req.description,
                'category': help_req.category,
                'city': help_req.city,
                'urgency': help_req.urgency,
                'true_priority': '',
                'true_best_ngo': ''
            })

            system_output_rows.append({
                'id': help_req.id,
                'system_priority': help_req.priority_label,
                'system_top_ngo': top_ngo_name,
                'system_is_duplicate': 1 if help_req.is_duplicate else 0,
                'system_is_suspicious': 1 if help_req.is_suspicious else 0,
                'is_duplicate_truth': meta['is_duplicate_truth'],
                'is_suspicious_truth': meta['is_suspicious_truth']
            })

        # Write dataset/to_label.csv
        to_label_path = os.path.join(dataset_dir, 'to_label.csv')
        with open(to_label_path, 'w', newline='', encoding='utf-8') as f1:
            fields1 = ['id', 'title', 'description', 'category', 'city', 'urgency', 'true_priority', 'true_best_ngo']
            w1 = csv.DictWriter(f1, fieldnames=fields1)
            w1.writeheader()
            for r in to_label_rows:
                w1.writerow(r)

        # Write dataset/system_output.csv
        system_output_path = os.path.join(dataset_dir, 'system_output.csv')
        with open(system_output_path, 'w', newline='', encoding='utf-8') as f2:
            fields2 = ['id', 'system_priority', 'system_top_ngo', 'system_is_duplicate', 'system_is_suspicious', 'is_duplicate_truth', 'is_suspicious_truth']
            w2 = csv.DictWriter(f2, fieldnames=fields2)
            w2.writeheader()
            for r in system_output_rows:
                w2.writerow(r)

        # Write dataset/ngo_list.csv
        ngo_list_path = os.path.join(dataset_dir, 'ngo_list.csv')
        with open(ngo_list_path, 'w', newline='', encoding='utf-8') as f3:
            fields3 = ['ngo_name', 'city', 'causes', 'rating']
            w3 = csv.DictWriter(f3, fieldnames=fields3)
            w3.writeheader()
            for ngo in ngo_profiles:
                w3.writerow({
                    'ngo_name': ngo.ngo_name,
                    'city': ngo.city,
                    'causes': ngo.causes,
                    'rating': ngo.rating
                })

        # 6. Print counts at the end
        self.stdout.write(self.style.SUCCESS(f"\n--- SEEDING COMPLETED SUCCESSFULLY ---"))
        self.stdout.write(f"Total Requests Created: {len(raw_requests_meta)}")
        self.stdout.write(f"Distinct Descriptions: {len(generated_texts)}")
        self.stdout.write(f"Priority Distribution: Critical={priority_counts['Critical']}, High={priority_counts['High']}, Normal={priority_counts['Normal']}")
        self.stdout.write(f"Duplicates Detected by System: {duplicate_count}")
        self.stdout.write(f"Datasets saved in: {dataset_dir}\n")
