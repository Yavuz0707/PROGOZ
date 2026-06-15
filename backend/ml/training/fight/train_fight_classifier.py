import argparse
import random
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import FightCNNLSTM  # noqa: E402


LABELS = {"non_violence": 0, "violence": 1}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class FightVideoDataset(Dataset):
    def __init__(self, root: Path, clip_len: int, frame_size: int) -> None:
        self.samples: list[tuple[Path, int]] = []
        self.clip_len = clip_len
        self.frame_size = frame_size
        for label, target in LABELS.items():
            class_dir = root / label
            if class_dir.exists():
                self.samples.extend((path, target) for path in class_dir.rglob("*") if path.suffix.lower() in VIDEO_EXTENSIONS)
        if not self.samples:
            raise RuntimeError(f"Video bulunamadi: {root}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):
        path, label = self.samples[index]
        clip = read_clip(path, self.clip_len, self.frame_size)
        return clip, torch.tensor(float(label), dtype=torch.float32)


def read_clip(path: Path, clip_len: int, frame_size: int) -> torch.Tensor:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Video acilamadi: {path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        indices = list(range(clip_len))
    else:
        indices = np.linspace(0, max(total - 1, 0), clip_len).astype(int).tolist()
    frames = []
    for frame_idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
        ok, frame = cap.read()
        if not ok:
            frame = np.zeros((frame_size, frame_size, 3), dtype=np.uint8)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (frame_size, frame_size), interpolation=cv2.INTER_AREA)
        frame = frame.astype(np.float32) / 255.0
        frame = (frame - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
        frames.append(torch.from_numpy(frame).permute(2, 0, 1))
    cap.release()
    return torch.stack(frames)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train PROGOZ fight/non-fight MobileNetV2+BiLSTM classifier.")
    parser.add_argument("--data", default="ml/datasets/fight/processed")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--clip-len", type=int, default=16)
    parser.add_argument("--frame-size", type=int, default=224)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="ml/models/fight/fight_classifier.pt")
    return parser.parse_args()


def train_epoch(model, loader, optimizer, criterion, device) -> float:
    model.train()
    losses = []
    for clips, labels in loader:
        clips, labels = clips.to(device), labels.to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(clips)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.item()))
    return sum(losses) / max(len(losses), 1)


@torch.no_grad()
def evaluate(model, loader, criterion, device) -> tuple[float, float]:
    model.eval()
    losses, correct, total = [], 0, 0
    for clips, labels in loader:
        clips, labels = clips.to(device), labels.to(device)
        logits = model(clips)
        loss = criterion(logits, labels)
        probs = torch.sigmoid(logits)
        preds = (probs >= 0.5).float()
        correct += int((preds == labels).sum().item())
        total += int(labels.numel())
        losses.append(float(loss.item()))
    return sum(losses) / max(len(losses), 1), correct / max(total, 1)


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    root = Path(__file__).resolve().parents[3]
    data_root = (root / args.data).resolve() if not Path(args.data).is_absolute() else Path(args.data)
    train_root, val_root = data_root / "train", data_root / "val"
    if not train_root.exists() or not val_root.exists():
        raise SystemExit(f"train/val klasorleri bulunamadi: {data_root}. Once prepare_fight_dataset.py calistirin.")
    device = torch.device(args.device if args.device == "cpu" or torch.cuda.is_available() else "cpu")
    if args.device.startswith("cuda") and device.type == "cpu":
        print("CUDA bulunamadi, CPU fallback kullaniliyor.")

    train_ds = FightVideoDataset(train_root, args.clip_len, args.frame_size)
    val_ds = FightVideoDataset(val_root, args.clip_len, args.frame_size)
    print(f"train_samples={len(train_ds)} val_samples={len(val_ds)} clip_len={args.clip_len} frame_size={args.frame_size} device={device}")
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)
    model = FightCNNLSTM().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    criterion = nn.BCEWithLogitsLoss()
    best_acc = 0.0
    out_path = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc = evaluate(model, val_loader, criterion, device)
        print(f"epoch={epoch:03d} train_loss={train_loss:.4f} val_loss={val_loss:.4f} val_acc={val_acc:.4f}")
        if val_acc >= best_acc:
            best_acc = val_acc
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "clip_len": args.clip_len,
                    "frame_size": args.frame_size,
                    "labels": LABELS,
                    "val_acc": best_acc,
                    "architecture": "MobileNetV2+BiLSTM",
                },
                out_path,
            )
            print(f"best model kaydedildi: {out_path}")


if __name__ == "__main__":
    main()
