import csv
import os
import random
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import HelpRequest, NGOProfile
from core.ai_engine import calculate_priority, match_score, haversine_km, DEFAULT_PARAMS
from core.management.commands.evaluate_ai import calculate_multiclass_metrics

CLASSES = ['Critical', 'High', 'Normal']

def evaluate_priority_rows(rows, params=None):
    """Run calculate_priority on a list of (row, HelpRequest) pairs and return accuracy, macro_f1, class_metrics."""
    y_true = []
    y_pred = []
    for row, req in rows:
        y_true.append(row['true_priority'].strip())
        _, pred_label = calculate_priority(
            req.title, req.description, req.category, req.urgency, params=params
        )
        y_pred.append(pred_label)
    acc, macro_f1, cm, class_metrics = calculate_multiclass_metrics(y_true, y_pred, CLASSES)
    return acc, macro_f1, cm, class_metrics

def evaluate_matching_rows(rows, candidate_ngos_map, params=None):
    """Run match_score on a list of (row, HelpRequest) pairs and return top1_acc, top3_acc, top1_hits, top3_hits."""
    total = len(rows)
    if total == 0:
        return 0.0, 0.0, 0, 0

    top1_hits = 0
    top3_hits = 0

    for row, req in rows:
        true_ngo = row['true_best_ngo'].strip().lower()
        candidates = candidate_ngos_map.get(req.id, [])
        if not candidates:
            continue

        scored = []
        for ngo in candidates:
            s = match_score(req, ngo, params=params)
            scored.append((ngo, s))

        # Sort high to low by score
        scored.sort(key=lambda x: x[1], reverse=True)
        top3_names = [ngo.ngo_name.strip().lower() for ngo, _ in scored[:3]]

        if top3_names and top3_names[0] == true_ngo:
            top1_hits += 1
        if true_ngo in top3_names:
            top3_hits += 1

    return top1_hits / total, top3_hits / total, top1_hits, top3_hits

class Command(BaseCommand):
    help = 'Tune priority and matching parameters on a tuning split and evaluate on a held-out test split.'

    def handle(self, *args, **options):
        dataset_dir = os.path.join(settings.BASE_DIR, 'dataset')
        labeled_path = os.path.join(dataset_dir, 'to_label_labeled.csv')

        if not os.path.exists(labeled_path):
            self.stdout.write(self.style.ERROR(
                f"Labeled file not found at {labeled_path}. Please save your labeled file as dataset/to_label_labeled.csv first."
            ))
            return

        # Read labeled CSV
        csv_rows = []
        with open(labeled_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                csv_rows.append(row)

        # Fetch HelpRequests from DB matching CSV ids
        requests_by_id = {req.id: req for req in HelpRequest.objects.all()}
        verified_ngos = list(NGOProfile.objects.filter(is_verified=True))

        # Build paired lists for priority and matching
        prio_pairs = []
        match_pairs = []
        missing_ids = 0

        for row in csv_rows:
            req_id_str = str(row.get('id', '')).strip()
            if not req_id_str.isdigit():
                continue
            req_id = int(req_id_str)
            req = requests_by_id.get(req_id)
            if not req:
                missing_ids += 1
                continue

            if row.get('true_priority', '').strip() in CLASSES:
                prio_pairs.append((row, req))
            if row.get('true_best_ngo', '').strip():
                match_pairs.append((row, req))

        if missing_ids > 0:
            self.stdout.write(self.style.WARNING(
                f"Warning: {missing_ids} CSV rows did not match any HelpRequest id in the database."
            ))

        # Split labelled rows 50/50 into TUNING and TEST halves with random.seed(42)
        random.seed(42)
        random.shuffle(prio_pairs)
        prio_mid = len(prio_pairs) // 2
        prio_tune = prio_pairs[:prio_mid]
        prio_test = prio_pairs[prio_mid:]

        random.seed(42)
        random.shuffle(match_pairs)
        match_mid = len(match_pairs) // 2
        match_tune = match_pairs[:match_mid]
        match_test = match_pairs[match_mid:]

        # Precompute eligible NGOs per request (same rule as get_top_matches)
        candidate_ngos_map = {}
        for _, req in match_pairs:
            matching_ngos = []
            for ngo in verified_ngos:
                causes = [c.strip().lower() for c in ngo.causes.split(',') if c.strip()]
                if req.category.lower() in causes:
                    matching_ngos.append(ngo)
            if not matching_ngos:
                matching_ngos = list(verified_ngos)
            candidate_ngos_map[req.id] = matching_ngos

        report_lines = []

        def log(msg=""):
            self.stdout.write(msg)
            report_lines.append(msg)

        log("==================================================")
        log("PHILANTHRO HEAVEN — AI TUNING & TEST REPORT")
        log("==================================================\n")

        # --------------------------------------------------
        # PART 1: PRIORITY TUNING
        # --------------------------------------------------
        log(f"1. PRIORITY TUNING (Total labelled: {len(prio_pairs)} | Tuning half: {len(prio_tune)} | Test half: {len(prio_test)})")
        if not prio_tune or not prio_test:
            log("   Not enough priority labels to tune and test.\n")
        else:
            # Grid values
            urgency_high_vals = [0.3, 0.4, 0.5]
            critical_bonus_vals = [0.2, 0.3, 0.4]
            critical_thresh_vals = [0.6, 0.7, 0.8]
            high_thresh_vals = [0.3, 0.4, 0.5]

            best_prio_params = None
            best_prio_tune_f1 = -1.0
            best_prio_tune_acc = -1.0

            for u_high in urgency_high_vals:
                for c_bonus in critical_bonus_vals:
                    for c_thresh in critical_thresh_vals:
                        for h_thresh in high_thresh_vals:
                            if h_thresh >= c_thresh:
                                continue
                            candidate_params = {
                                'urgency_high': u_high,
                                'critical_bonus': c_bonus,
                                'critical_threshold': c_thresh,
                                'high_threshold': h_thresh,
                            }
                            acc, macro_f1, _, _ = evaluate_priority_rows(prio_tune, params=candidate_params)
                            if (macro_f1 > best_prio_tune_f1) or (macro_f1 == best_prio_tune_f1 and acc > best_prio_tune_acc):
                                best_prio_tune_f1 = macro_f1
                                best_prio_tune_acc = acc
                                best_prio_params = candidate_params

            # Evaluate default vs best on both tuning and test halves
            def_tune_acc, def_tune_f1, _, _ = evaluate_priority_rows(prio_tune, params=None)
            def_test_acc, def_test_f1, _, def_test_cm = evaluate_priority_rows(prio_test, params=None)
            best_test_acc, best_test_f1, _, best_test_cm = evaluate_priority_rows(prio_test, params=best_prio_params)

            # Baseline on test half: urgency field only (high=Critical, medium=High, low=Normal)
            urg_true = [row['true_priority'].strip() for row, _ in prio_test]
            urg_pred = []
            for row, req in prio_test:
                u = req.urgency.strip().lower()
                if u == 'high':
                    urg_pred.append('Critical')
                elif u == 'medium':
                    urg_pred.append('High')
                else:
                    urg_pred.append('Normal')
            base_urg_acc, base_urg_f1, _, _ = calculate_multiclass_metrics(urg_true, urg_pred, CLASSES)

            log(f"   Default Params: urgency_high={DEFAULT_PARAMS['urgency_high']}, critical_bonus={DEFAULT_PARAMS['critical_bonus']}, "
                f"critical_threshold={DEFAULT_PARAMS['critical_threshold']}, high_threshold={DEFAULT_PARAMS['high_threshold']}")
            log(f"   Best Params   : urgency_high={best_prio_params['urgency_high']}, critical_bonus={best_prio_params['critical_bonus']}, "
                f"critical_threshold={best_prio_params['critical_threshold']}, high_threshold={best_prio_params['high_threshold']}\n")

            log(f"   {'Split':<12} {'Config':<22} {'Accuracy':<12} {'Macro F1':<12}")
            log(f"   {'-'*58}")
            log(f"   {'Tuning':<12} {'Default':<22} {def_tune_acc:<12.4f} {def_tune_f1:<12.4f}")
            log(f"   {'Tuning':<12} {'Best Tuned':<22} {best_prio_tune_acc:<12.4f} {best_prio_tune_f1:<12.4f}")
            log(f"   {'Test':<12} {'Default':<22} {def_test_acc:<12.4f} {def_test_f1:<12.4f}")
            log(f"   {'Test':<12} {'Best Tuned':<22} {best_test_acc:<12.4f} {best_test_f1:<12.4f}")
            log(f"   {'Test':<12} {'Baseline (Urgency)':<22} {base_urg_acc:<12.4f} {base_urg_f1:<12.4f}\n")

            log("   Test-Half Per-Class F1 (Default -> Best Tuned):")
            for c in CLASSES:
                log(f"     - {c:<9}: {def_test_cm[c]['f1']:.4f} -> {best_test_cm[c]['f1']:.4f}")
            log("")

        # --------------------------------------------------
        # PART 2: MATCHING WEIGHTS TUNING
        # --------------------------------------------------
        log(f"2. MATCHING TUNING (Total labelled: {len(match_pairs)} | Tuning half: {len(match_tune)} | Test half: {len(match_test)})")
        if not match_tune or not match_test:
            log("   Not enough NGO labels to tune and test.\n")
        else:
            best_match_params = None
            best_match_tune_top1 = -1.0
            best_match_tune_top3 = -1.0
            combos_tried = 0

            # Each weight from 0.05 (1*0.05) to 0.60 (12*0.05), summing to 1.00 (20*0.05)
            for c_step in range(1, 13):
                for u_step in range(1, 13):
                    for p_step in range(1, 13):
                        t_step = 20 - c_step - u_step - p_step
                        if 1 <= t_step <= 12:
                            combos_tried += 1
                            w_params = {
                                'category': round(c_step * 0.05, 2),
                                'urgency': round(u_step * 0.05, 2),
                                'proximity': round(p_step * 0.05, 2),
                                'trust': round(t_step * 0.05, 2),
                            }
                            top1_acc, top3_acc, _, _ = evaluate_matching_rows(match_tune, candidate_ngos_map, params=w_params)
                            if (top1_acc > best_match_tune_top1) or (top1_acc == best_match_tune_top1 and top3_acc > best_match_tune_top3):
                                best_match_tune_top1 = top1_acc
                                best_match_tune_top3 = top3_acc
                                best_match_params = w_params

            def_tune_t1, def_tune_t3, _, _ = evaluate_matching_rows(match_tune, candidate_ngos_map, params=None)
            def_test_t1, def_test_t3, def_t1_hits, def_t3_hits = evaluate_matching_rows(match_test, candidate_ngos_map, params=None)
            best_test_t1, best_test_t3, best_t1_hits, best_t3_hits = evaluate_matching_rows(match_test, candidate_ngos_map, params=best_match_params)

            # Baseline on test half: nearest NGO that supports the request category
            base_hits = 0
            for row, req in match_test:
                true_ngo = row['true_best_ngo'].strip().lower()
                candidates = candidate_ngos_map.get(req.id, [])
                if candidates:
                    nearest = min(
                        candidates,
                        key=lambda ngo: haversine_km(req.latitude, req.longitude, ngo.latitude, ngo.longitude)
                    )
                    if nearest.ngo_name.strip().lower() == true_ngo:
                        base_hits += 1
            base_test_t1 = base_hits / len(match_test)

            log(f"   Weight combinations tested: {combos_tried}")
            log(f"   Default Weights: category={DEFAULT_PARAMS['category']}, urgency={DEFAULT_PARAMS['urgency']}, "
                f"proximity={DEFAULT_PARAMS['proximity']}, trust={DEFAULT_PARAMS['trust']}")
            log(f"   Best Weights   : category={best_match_params['category']}, urgency={best_match_params['urgency']}, "
                f"proximity={best_match_params['proximity']}, trust={best_match_params['trust']}\n")

            log(f"   {'Split':<12} {'Config':<28} {'Top-1 Acc':<14} {'Top-3 Acc':<14}")
            log(f"   {'-'*68}")
            log(f"   {'Tuning':<12} {'Default':<28} {def_tune_t1:<14.4f} {def_tune_t3:<14.4f}")
            log(f"   {'Tuning':<12} {'Best Tuned':<28} {best_match_tune_top1:<14.4f} {best_match_tune_top3:<14.4f}")
            log(f"   {'Test':<12} {'Default':<28} {def_test_t1:<14.4f} {def_test_t3:<14.4f}")
            log(f"   {'Test':<12} {'Best Tuned':<28} {best_test_t1:<14.4f} {best_test_t3:<14.4f}")
            log(f"   {'Test':<12} {'Baseline (Nearest in Cat.)':<28} {base_test_t1:<14.4f} {'N/A':<14}\n")
            log(f"   Test-Half Top-1 Hits: Default={def_t1_hits}/{len(match_test)}, Best Tuned={best_t1_hits}/{len(match_test)}, Baseline={base_hits}/{len(match_test)}")
            log(f"   Test-Half Top-3 Hits: Default={def_t3_hits}/{len(match_test)}, Best Tuned={best_t3_hits}/{len(match_test)}\n")

        log("==================================================")
        log("TUNING COMPLETE (ai_engine.py defaults unchanged)")
        log("==================================================")

        report_path = os.path.join(dataset_dir, 'tuning_report.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(report_lines))

        self.stdout.write(self.style.SUCCESS(f"\nTuning report saved to {report_path}"))
