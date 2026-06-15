import argparse
import json
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import FightCNNLSTM  # noqa: E402
from train_fight_classifier import FightVideoDataset  # noqa: E402


def metrics_from_counts(tp: int, tn: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    accuracy = (tp + tn) / max(tp + tn + fp + fn, 1)
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PROGOZ fight classifier.")
    parser.add_argument("--model", default="ml/models/fight/fight_classifier.pt")
    parser.add_argument("--data", default="ml/datasets/fight/processed/test")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--report", default="ml/runs/fight/evaluation_report.json")
    parser.add_argument("--max-examples", type=int, default=30)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    model_path = (root / args.model).resolve() if not Path(args.model).is_absolute() else Path(args.model)
    data_root = (root / args.data).resolve() if not Path(args.data).is_absolute() else Path(args.data)
    if not model_path.exists():
        raise SystemExit(f"Model bulunamadi: {model_path}")
    if not data_root.exists():
        raise SystemExit(f"Test dataset bulunamadi: {data_root}")

    checkpoint = torch.load(model_path, map_location="cpu")
    clip_len = int(checkpoint.get("clip_len", 16))
    frame_size = int(checkpoint.get("frame_size", 224))
    dataset = FightVideoDataset(data_root, clip_len, frame_size)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)
    device = torch.device(args.device if args.device == "cpu" or torch.cuda.is_available() else "cpu")
    model = FightCNNLSTM().to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    tp = tn = fp = fn = 0
    false_positives, false_negatives = [], []
    cursor = 0
    with torch.no_grad():
        for clips, labels in loader:
            clips = clips.to(device)
            probs = torch.sigmoid(model(clips)).cpu()
            for prob, label in zip(probs, labels):
                path, _ = dataset.samples[cursor]
                cursor += 1
                pred = int(float(prob) >= args.threshold)
                target = int(float(label))
                if pred == 1 and target == 1:
                    tp += 1
                elif pred == 0 and target == 0:
                    tn += 1
                elif pred == 1 and target == 0:
                    fp += 1
                    false_positives.append((str(path), float(prob)))
                else:
                    fn += 1
                    false_negatives.append((str(path), float(prob)))

    metrics = metrics_from_counts(tp, tn, fp, fn)
    report = {
        "model": str(model_path),
        "data": str(data_root),
        "threshold": args.threshold,
        "metrics": metrics,
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "false_positive_examples": [{"path": path, "violence_probability": prob} for path, prob in false_positives[: args.max_examples]],
        "false_negative_examples": [{"path": path, "violence_probability": prob} for path, prob in false_negatives[: args.max_examples]],
    }
    print("metrics:")
    for name, value in metrics.items():
        print(f"  {name}: {value:.4f}")
    print(f"confusion_matrix: TP={tp} TN={tn} FP={fp} FN={fn}")
    print("false_positive_examples:")
    for path, prob in false_positives[: args.max_examples]:
        print(f"  {prob:.3f} {path}")
    print("false_negative_examples:")
    for path, prob in false_negatives[: args.max_examples]:
        print(f"  {prob:.3f} {path}")
    report_path = (root / args.report).resolve() if not Path(args.report).is_absolute() else Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"evaluation_report: {report_path}")


if __name__ == "__main__":
    main()
