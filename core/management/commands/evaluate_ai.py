import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import HelpRequest, NGOProfile, Match
from core.ai_engine import haversine_km

def calculate_binary_metrics(y_true, y_pred):
    """Calculate TP, FP, FN, TN, precision, recall, and F1 for binary classification."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return tp, fp, fn, tn, precision, recall, f1

def calculate_multiclass_metrics(y_true, y_pred, classes):
    """Calculate accuracy, macro F1, confusion matrix, and per-class metrics for multiclass classification."""
    total = len(y_true)
    if total == 0:
        return 0.0, 0.0, [], {}

    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / total

    # Confusion matrix: rows = true, columns = system (predicted)
    # classes order: Critical, High, Normal
    class_to_idx = {c: i for i, c in enumerate(classes)}
    n_classes = len(classes)
    cm = [[0] * n_classes for _ in range(n_classes)]

    for t, p in zip(y_true, y_pred):
        if t in class_to_idx and p in class_to_idx:
            cm[class_to_idx[t]][class_to_idx[p]] += 1

    class_metrics = {}
    f1_sum = 0.0

    for c in classes:
        idx = class_to_idx[c]
        # True positives for class c
        tp = cm[idx][idx]
        # False positives: sum of column c excluding diagonal
        fp = sum(cm[r][idx] for r in range(n_classes) if r != idx)
        # False negatives: sum of row c excluding diagonal
        fn = sum(cm[idx][col] for col in range(n_classes) if col != idx)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        class_metrics[c] = {'precision': prec, 'recall': rec, 'f1': f1}
        f1_sum += f1

    macro_f1 = f1_sum / n_classes if n_classes > 0 else 0.0

    return accuracy, macro_f1, cm, class_metrics

class Command(BaseCommand):
    help = 'Evaluates AI system performance against labeled datasets and baselines'

    def handle(self, *args, **options):
        dataset_dir = os.path.join(settings.BASE_DIR, 'dataset')
        to_labeled_path = os.path.join(dataset_dir, 'to_label_labeled.csv')
        system_output_path = os.path.join(dataset_dir, 'system_output.csv')
        ngo_list_path = os.path.join(dataset_dir, 'ngo_list.csv')

        if not os.path.exists(to_labeled_path):
            self.stdout.write(self.style.ERROR(
                f"Labeled file not found at {to_labeled_path}. Please save your labeled file as dataset/to_label_labeled.csv and run again."
            ))
            return

        # Load datasets with encoding="utf-8-sig", newline=""
        labeled_data = {}
        with open(to_labeled_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                labeled_data[str(row['id']).strip()] = row

        system_data = {}
        if os.path.exists(system_output_path):
            with open(system_output_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    system_data[str(row['id']).strip()] = row

        report_lines = []

        def log(msg=""):
            self.stdout.write(msg)
            report_lines.append(msg)

        log("==================================================")
        log("PHILANTHRO HEAVEN — AI EVALUATION REPORT")
        log("==================================================\n")

        # --------------------------------------------------
        # PART 1: DUPLICATE DETECTION EVALUATION
        # --------------------------------------------------
        dup_y_true = []
        dup_y_pred = []
        for req_id, row in labeled_data.items():
            sys_row = system_data.get(req_id, {})
            # the truth columns are stored in system_output.csv
            is_dup_str = (sys_row.get('is_duplicate_truth') or row.get('is_duplicate_truth', '')).strip()
            if is_dup_str in ['0', '1']:
                true_val = int(is_dup_str)
                sys_val = int(sys_row.get('system_is_duplicate', 0))
                dup_y_true.append(true_val)
                dup_y_pred.append(sys_val)

        n_dup = len(dup_y_true)
        log(f"1. DUPLICATE DETECTION (Rows used: {n_dup})")
        if n_dup > 0:
            tp, fp, fn, tn, prec, rec, f1 = calculate_binary_metrics(dup_y_true, dup_y_pred)
            log(f"   TP: {tp} | FP: {fp} | FN: {fn} | TN: {tn}")
            log(f"   Precision: {prec:.4f} | Recall: {rec:.4f} | F1-score: {f1:.4f}")
            log("   Confusion Matrix (Rows = True, Columns = System):")
            log(f"                Predicted 0    Predicted 1")
            log(f"   Actual 0     {tn:<14} {fp:<14}")
            log(f"   Actual 1     {fn:<14} {tp:<14}\n")
        else:
            log("   No duplicate truth labels found.\n")

        # --------------------------------------------------
        # PART 2: SUSPICIOUS DETECTION EVALUATION
        # --------------------------------------------------
        susp_y_true = []
        susp_y_pred = []
        for req_id, row in labeled_data.items():
            sys_row = system_data.get(req_id, {})
            is_susp_str = (sys_row.get('is_suspicious_truth') or row.get('is_suspicious_truth', '')).strip()
            if is_susp_str in ['0', '1']:
                true_val = int(is_susp_str)
                sys_val = int(sys_row.get('system_is_suspicious', 0))
                susp_y_true.append(true_val)
                susp_y_pred.append(sys_val)

        n_susp = len(susp_y_true)
        log(f"2. SUSPICIOUS DETECTION (Rows used: {n_susp})")
        if n_susp > 0:
            tp, fp, fn, tn, prec, rec, f1 = calculate_binary_metrics(susp_y_true, susp_y_pred)
            log(f"   TP: {tp} | FP: {fp} | FN: {fn} | TN: {tn}")
            log(f"   Precision: {prec:.4f} | Recall: {rec:.4f} | F1-score: {f1:.4f}")
            log("   Confusion Matrix (Rows = True, Columns = System):")
            log(f"                Predicted 0    Predicted 1")
            log(f"   Actual 0     {tn:<14} {fp:<14}")
            log(f"   Actual 1     {fn:<14} {tp:<14}\n")
        else:
            log("   No suspicious truth labels found.\n")

        # --------------------------------------------------
        # PART 3: PRIORITY EVALUATION
        # --------------------------------------------------
        classes = ['Critical', 'High', 'Normal']
        prio_y_true = []
        prio_y_pred = []
        urgency_preds = []
        normal_preds = []

        for req_id, row in labeled_data.items():
            true_prio = row.get('true_priority', '').strip()
            if true_prio in classes:
                prio_y_true.append(true_prio)
                sys_row = system_data.get(req_id, {})
                sys_prio = sys_row.get('system_priority', 'Normal').strip()
                if sys_prio not in classes:
                    sys_prio = 'Normal'
                prio_y_pred.append(sys_prio)

                # Baseline (a): Always predict Normal
                normal_preds.append('Normal')

                # Baseline (b): Urgency field only (high=Critical, medium=High, low=Normal)
                urg = row.get('urgency', 'medium').strip().lower()
                if urg == 'high':
                    urgency_preds.append('Critical')
                elif urg == 'medium':
                    urgency_preds.append('High')
                else:
                    urgency_preds.append('Normal')

        n_prio = len(prio_y_true)
        log(f"3. PRIORITY EVALUATION (Rows used: {n_prio})")
        if n_prio == 0:
            log("   Priority labels not filled yet.\n")
        else:
            acc, macro_f1, cm, class_metrics = calculate_multiclass_metrics(prio_y_true, prio_y_pred, classes)
            log(f"   System Accuracy: {acc:.4f} | Macro F1: {macro_f1:.4f}")
            log("   Per-Class Metrics:")
            for c in classes:
                m = class_metrics[c]
                log(f"     - {c:<9}: Precision={m['precision']:.4f}, Recall={m['recall']:.4f}, F1={m['f1']:.4f}")

            log("\n   3x3 Confusion Matrix (Rows = True, Columns = System):")
            log(f"               Pred Critical   Pred High      Pred Normal")
            for i, c in enumerate(classes):
                log(f"   Actual {c:<9} {cm[i][0]:<14} {cm[i][1]:<14} {cm[i][2]:<14}")

            # Baselines
            base_norm_acc, base_norm_f1, _, _ = calculate_multiclass_metrics(prio_y_true, normal_preds, classes)
            base_urg_acc, base_urg_f1, _, _ = calculate_multiclass_metrics(prio_y_true, urgency_preds, classes)
            log(f"\n   Baselines:")
            log(f"     (a) Always Predict Normal : Accuracy = {base_norm_acc:.4f}, Macro F1 = {base_norm_f1:.4f}")
            log(f"     (b) Urgency Field Only    : Accuracy = {base_urg_acc:.4f}, Macro F1 = {base_urg_f1:.4f}\n")

        # --------------------------------------------------
        # PART 4: MATCHING EVALUATION
        # --------------------------------------------------
        match_rows_evaluated = 0
        top1_correct = 0
        top3_correct = 0

        base_a_top1_correct = 0 # Nearest NGO among all verified
        base_b_top1_correct = 0 # Nearest NGO among those whose causes include category

        verified_ngos = list(NGOProfile.objects.filter(is_verified=True))

        for req_id, row in labeled_data.items():
            true_ngo_name = row.get('true_best_ngo', '').strip()
            if not true_ngo_name:
                continue

            match_rows_evaluated += 1
            help_req = HelpRequest.objects.filter(id=req_id).first()
            if not help_req:
                continue

            # System top 3 matches
            system_matches = Match.objects.filter(request=help_req).order_by('rank')[:3]
            sys_top3_names = [m.ngo.ngo_name.strip() for m in system_matches]

            if sys_top3_names and sys_top3_names[0].lower() == true_ngo_name.lower():
                top1_correct += 1
            if any(name.lower() == true_ngo_name.lower() for name in sys_top3_names):
                top3_correct += 1

            # Baseline (a): Nearest NGO by haversine distance among all verified NGOs
            if verified_ngos:
                nearest_a = min(verified_ngos, key=lambda ngo: haversine_km(help_req.latitude, help_req.longitude, ngo.latitude, ngo.longitude))
                if nearest_a.ngo_name.strip().lower() == true_ngo_name.lower():
                    base_a_top1_correct += 1

            # Baseline (b): Nearest NGO among those whose causes include the request category
            matching_ngos_b = [
                ngo for ngo in verified_ngos 
                if help_req.category.lower() in [c.strip().lower() for c in ngo.causes.split(',') if c.strip()]
            ]
            if not matching_ngos_b:
                matching_ngos_b = verified_ngos # Fallback

            if matching_ngos_b:
                nearest_b = min(matching_ngos_b, key=lambda ngo: haversine_km(help_req.latitude, help_req.longitude, ngo.latitude, ngo.longitude))
                if nearest_b.ngo_name.strip().lower() == true_ngo_name.lower():
                    base_b_top1_correct += 1

        log(f"4. MATCHING EVALUATION (Rows used: {match_rows_evaluated})")
        if match_rows_evaluated == 0:
            log("   NGO labels not filled yet.\n")
        else:
            top1_acc = top1_correct / match_rows_evaluated
            top3_acc = top3_correct / match_rows_evaluated
            base_a_acc = base_a_top1_correct / match_rows_evaluated
            base_b_acc = base_b_top1_correct / match_rows_evaluated

            log(f"   System Top-1 Accuracy: {top1_acc:.4f} ({top1_correct}/{match_rows_evaluated})")
            log(f"   System Top-3 Accuracy: {top3_acc:.4f} ({top3_correct}/{match_rows_evaluated})")
            log(f"   Baselines (Top-1 Accuracy):")
            log(f"     (a) Nearest NGO (All Verified)          : {base_a_acc:.4f} ({base_a_top1_correct}/{match_rows_evaluated})")
            log(f"     (b) Nearest NGO (Matching Category Causes): {base_b_acc:.4f} ({base_b_top1_correct}/{match_rows_evaluated})\n")

        log("==================================================")
        log("EVALUATION COMPLETE")
        log("==================================================")

        # Save evaluation report to dataset/evaluation_report.txt
        report_path = os.path.join(dataset_dir, 'evaluation_report.txt')
        with open(report_path, 'w', encoding='utf-8') as rep_file:
            rep_file.write("\n".join(report_lines))

        self.stdout.write(self.style.SUCCESS(f"\nEvaluation report successfully saved to {report_path}"))
