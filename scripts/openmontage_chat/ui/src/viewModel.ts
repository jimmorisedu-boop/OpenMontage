import type { Artifact, Material, ProjectState, ProjectStatus } from "./types";

export const STATUS_COPY: Record<ProjectStatus, { label: string; stage: number; tone: string }> = {
  needs_brief: { label: "Нужны уточнения", stage: 1, tone: "attention" },
  ready_to_plan: { label: "Готов к плану", stage: 2, tone: "active" },
  awaiting_approval: { label: "План на проверке", stage: 3, tone: "attention" },
  running: { label: "Монтаж выполняется", stage: 4, tone: "active" },
  needs_attention: { label: "Нужно внимание", stage: 4, tone: "danger" },
  ready: { label: "Монтаж готов", stage: 5, tone: "success" },
};

export const STAGES = ["Задача", "Материалы", "План", "Монтаж", "Результат"];

export function statusCopy(status: string | undefined) {
  return STATUS_COPY[(status || "needs_brief") as ProjectStatus] || STATUS_COPY.needs_brief;
}

export function playableArtifact(project: ProjectState): Artifact | null {
  const candidates = [
    project.verified_artifact,
    ...(project.verified_artifacts || []),
    ...(project.artifacts_state?.verified || []),
  ].filter(Boolean) as Artifact[];
  return candidates.find((item) => /\.(mp4|mov|mkv|webm)$/i.test(item.path || item.name || "")) || null;
}

export function allArtifacts(project: ProjectState): Artifact[] {
  const values = [
    ...(project.verified_artifacts || []),
    ...(project.artifacts_state?.verified || []),
    ...(project.verified_artifact ? [project.verified_artifact] : []),
  ];
  return Array.from(new Map(values.map((item) => [item.artifact_id || item.path, item])).values());
}

export function groupMaterials(materials: Material[]) {
  const groups: Record<string, Material[]> = { video: [], audio: [], image: [], document: [] };
  materials.forEach((item) => {
    const kind = item.kind || item.media_type || "document";
    (groups[kind] || groups.document).push(item);
  });
  return groups;
}

export function fileUrl(path: string) {
  const normalized = path.replace(/\\/g, "/");
  return encodeURI(`file:///${normalized.replace(/^\/+/, "")}`);
}

export function bytes(value?: number) {
  if (!value) return "";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit += 1; }
  return `${amount >= 10 || unit === 0 ? amount.toFixed(0) : amount.toFixed(1)} ${units[unit]}`;
}

export function timecode(value?: number) {
  const seconds = Math.max(0, Math.round(value || 0));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function operationProgress(current?: number, total?: number) {
  if (!total) return 8;
  return Math.max(4, Math.min(100, Math.round(((current || 0) / total) * 100)));
}
