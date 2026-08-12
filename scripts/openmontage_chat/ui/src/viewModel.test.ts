import { describe, expect, it } from "vitest";
import type { ProjectState } from "./types";
import { fileUrl, groupMaterials, operationProgress, playableArtifact, statusCopy } from "./viewModel";

const project = (changes: Partial<ProjectState> = {}): ProjectState => ({
  project_id: "fixture", title: "Fixture", status: "needs_brief", project_root: "C:\\fixture",
  projects: [], conversation: [], ...changes,
});

describe("studio view model", () => {
  it("chooses only playable verified video artifacts", () => {
    const video = { artifact_id: "v", path: "C:\\renders\\final.mp4", verified: true };
    expect(playableArtifact(project({ artifacts_state: { verified: [{ artifact_id: "j", path: "C:\\report.json" }, video] } }))).toEqual(video);
  });

  it("keeps every material category visible", () => {
    const grouped = groupMaterials([{ path: "a.mov", kind: "video" }, { path: "brief.pdf", kind: "document" }]);
    expect(grouped.video).toHaveLength(1);
    expect(grouped.document).toHaveLength(1);
    expect(grouped.audio).toEqual([]);
  });

  it("normalizes Windows paths and clamps operation progress", () => {
    expect(fileUrl("F:\\Project Files\\final.mp4")).toBe("file:///F:/Project%20Files/final.mp4");
    expect(operationProgress(12, 10)).toBe(100);
    expect(operationProgress(0, 10)).toBe(4);
  });

  it("uses truthful stage copy for known and unknown states", () => {
    expect(statusCopy("ready").stage).toBe(5);
    expect(statusCopy("unknown").label).toBe(statusCopy("needs_brief").label);
  });
});
