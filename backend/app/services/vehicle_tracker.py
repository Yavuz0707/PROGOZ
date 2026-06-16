"""Centroid bazli arac takibi (vehicle tracking).

Her plaka tespiti icin benzersiz bir vehicle_id atar. Ayni arac farkli
frame'lerde gorunse bile centroid yakinligina gore ayni vehicle_id'yi
korur. Ayni goruntude birden fazla arac varsa her biri kendi
vehicle_id'sine gore ayri takip edilir ve plaka oylari karismaz.

Bu katman mevcut plaka deduplication/fuzzy-matching mantigina dokunmaz;
sadece ek metadata (vehicle_id + arac rengi) saglar.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrackedVehicle:
    vehicle_id: str  # orn: "V-001", "V-002"
    last_bbox: tuple  # (x1, y1, x2, y2)
    last_seen_at: float
    color_name: str = "Bilinmiyor"
    color_hex: str = "#888888"
    plate_votes: dict = field(default_factory=dict)
    # plate_votes: {plate_text: {"confidence": float, "count": int}}


class VehicleTracker:
    def __init__(self, max_distance: float = 100.0, max_age_seconds: float = 5.0):
        self.vehicles: dict[str, TrackedVehicle] = {}
        self.next_id = 1
        self.max_distance = max_distance
        self.max_age_seconds = max_age_seconds

    def _centroid(self, bbox):
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def _distance(self, c1, c2):
        return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5

    def update(
        self,
        bbox: tuple,
        plate_text: str,
        confidence: float,
        frame_crop=None,
    ) -> str:
        """Yeni bir plaka tespiti geldiginde cagrilir.

        En yakin mevcut araci bulur veya yeni arac olusturur.
        Returns: vehicle_id
        """
        now = time.time()
        centroid = self._centroid(bbox)

        # Suresi dolmus araclari temizle
        expired = [
            vid for vid, v in self.vehicles.items()
            if now - v.last_seen_at > self.max_age_seconds
        ]
        for vid in expired:
            del self.vehicles[vid]

        # En yakin araci bul
        best_match = None
        best_dist = self.max_distance
        for vid, vehicle in self.vehicles.items():
            dist = self._distance(centroid, self._centroid(vehicle.last_bbox))
            if dist < best_dist:
                best_dist = dist
                best_match = vid

        if best_match:
            vehicle = self.vehicles[best_match]
            vehicle.last_bbox = bbox
            vehicle.last_seen_at = now
        else:
            best_match = f"V-{self.next_id:03d}"
            self.next_id += 1
            color_name, color_hex = ("Bilinmiyor", "#888888")
            if frame_crop is not None:
                color_name, color_hex = self._detect_color(frame_crop)
            self.vehicles[best_match] = TrackedVehicle(
                vehicle_id=best_match,
                last_bbox=bbox,
                last_seen_at=now,
                color_name=color_name,
                color_hex=color_hex,
            )
            vehicle = self.vehicles[best_match]

        # Plaka oy ekle (vote buffer mantigi - her arac icin ayri)
        if not plate_text:
            return best_match
        if plate_text not in vehicle.plate_votes:
            vehicle.plate_votes[plate_text] = {"confidence": confidence, "count": 1}
        else:
            entry = vehicle.plate_votes[plate_text]
            entry["count"] += 1
            if confidence > entry["confidence"]:
                entry["confidence"] = confidence

        return best_match

    def get_best_plate(self, vehicle_id: str) -> Optional[dict]:
        """Bu arac icin en yuksek confidence'li plakayi dondur."""
        vehicle = self.vehicles.get(vehicle_id)
        if not vehicle or not vehicle.plate_votes:
            return None
        best_text = max(
            vehicle.plate_votes.items(),
            key=lambda x: (x[1]["confidence"], x[1]["count"]),
        )
        return {
            "plate_text": best_text[0],
            "confidence": best_text[1]["confidence"],
            "count": best_text[1]["count"],
        }

    def get_vehicle_meta(self, vehicle_id: str) -> Optional[dict]:
        """Bir arac icin metadata (id + renk) dondur."""
        vehicle = self.vehicles.get(vehicle_id)
        if not vehicle:
            return None
        return {
            "vehicle_id": vehicle.vehicle_id,
            "color_name": vehicle.color_name,
            "color_hex": vehicle.color_hex,
        }

    def find_vehicle_for_plate(self, plate_text: str) -> Optional[dict]:
        """Verilen plaka metnine sahip araci bul ve metadata'sini dondur.

        Final/interim DB yazimlari sirasinda kazanan plaka metnine ait
        arac kimligini ve rengini eslestirmek icin kullanilir.
        """
        if not plate_text:
            return None
        target = plate_text.strip().upper()
        for vehicle in self.vehicles.values():
            for vote_text in vehicle.plate_votes:
                if (vote_text or "").strip().upper() == target:
                    return {
                        "vehicle_id": vehicle.vehicle_id,
                        "color_name": vehicle.color_name,
                        "color_hex": vehicle.color_hex,
                    }
        return None

    def _detect_color(self, frame_crop) -> tuple[str, str]:
        """Plaka cevresindeki bolgenin dominant rengini tespit et.

        frame_crop: plaka bbox'inin ~3x genisletilmis crop'u (BGR numpy array)
        Returns: (renk_adi_turkce, hex_kod)
        """
        try:
            import cv2
            import numpy as np

            if frame_crop is None or getattr(frame_crop, "size", 0) == 0:
                return ("Bilinmiyor", "#888888")

            # K-means ile dominant renk
            small = cv2.resize(frame_crop, (50, 50))
            pixels = small.reshape(-1, 3).astype(np.float32)

            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
            _, labels, centers = cv2.kmeans(
                pixels, 3, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS
            )

            # En sik gecen cluster'i al
            counts = np.bincount(labels.flatten())
            dominant = centers[np.argmax(counts)]
            b, g, r = dominant.astype(int)
            hex_code = f"#{r:02x}{g:02x}{b:02x}"

            # Renk adi eslestirme (basit HSV bazli)
            hsv = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0][0]
            h, s, v = int(hsv[0]), int(hsv[1]), int(hsv[2])

            color_name = self._hsv_to_color_name(h, s, v)
            return (color_name, hex_code)
        except Exception:
            return ("Bilinmiyor", "#888888")

    def _hsv_to_color_name(self, h, s, v) -> str:
        if v < 50:
            return "Siyah"
        if v > 200 and s < 30:
            return "Beyaz"
        if s < 40:
            return "Gri"
        if h < 10 or h > 170:
            return "Kirmizi"
        if 10 <= h < 25:
            return "Turuncu"
        if 25 <= h < 35:
            return "Sari"
        if 35 <= h < 85:
            return "Yesil"
        if 85 <= h < 130:
            return "Mavi"
        if 130 <= h < 170:
            return "Mor"
        return "Bilinmiyor"


def expand_bbox_crop(frame, bbox, scale: float = 3.0):
    """Plaka bbox'ini ~scale kati genisletip aracin govdesini kapsayan crop dondur.

    frame: BGR numpy array. bbox: (x1, y1, x2, y2). Hata durumunda None dondurur.
    """
    try:
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1
        if w <= 0 or h <= 0:
            return None
        pad_x = int(w * (scale - 1) / 2)
        pad_y = int(h * (scale - 1) / 2)
        height, width = frame.shape[:2]
        nx1 = max(0, int(x1) - pad_x)
        ny1 = max(0, int(y1) - pad_y)
        nx2 = min(width, int(x2) + pad_x)
        ny2 = min(height, int(y2) + pad_y)
        if nx2 <= nx1 or ny2 <= ny1:
            return None
        return frame[ny1:ny2, nx1:nx2].copy()
    except Exception:
        return None
