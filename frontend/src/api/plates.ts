import { api, unwrap } from "./client";
import type { PlateRecord, PlateStats } from "../types";

export type PlateFilters = {
  source_type?: string;
  camera_id?: number;
  analysis_job_id?: number;
  plate?: string;
  valid_only?: boolean;
  show_unreadable?: boolean;
  require_valid_format?: boolean;
  date_from?: string;
  date_to?: string;
  min_confidence?: number;
};

export function getPlates(filters: PlateFilters) {
  return unwrap<PlateRecord[]>(api.get("/plates", { params: filters }));
}

export function getPlateStats() {
  return unwrap<PlateStats>(api.get("/plates/stats"));
}

export function cleanupUnreadablePlates() {
  return unwrap<{ deleted: number }>(api.post("/plates/cleanup-unreadable"));
}
