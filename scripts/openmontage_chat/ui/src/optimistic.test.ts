import { describe, expect, it } from "vitest";
import type { ProjectState } from "./types";
import { withOptimisticCommand } from "./optimistic";

const project: ProjectState = {
  project_id: "p1", title: "Test", status: "needs_brief", project_root: "C:\\project",
  projects: [], conversation: [],
};

describe("optimistic command history", () => {
  it("shows a submitted user command immediately without mutating server state", () => {
    const visible = withOptimisticCommand(project, "  Сделай динамичный тизер  ");

    expect(visible.conversation).toHaveLength(1);
    expect(visible.conversation[0]).toMatchObject({ role: "user", type: "text", text: "Сделай динамичный тизер", pending: true });
    expect(project.conversation).toEqual([]);
  });

  it("does not duplicate the same command when it is already last in history", () => {
    const saved = { ...project, conversation: [{ role: "user" as const, type: "text", text: "Сделай тизер" }] };

    expect(withOptimisticCommand(saved, "Сделай тизер").conversation).toHaveLength(1);
  });
});
