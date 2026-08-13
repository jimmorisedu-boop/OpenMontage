import type { ProjectState } from "./types";

export function withOptimisticCommand(project: ProjectState, message: string): ProjectState {
  const text = message.trim();
  const last = project.conversation.at(-1);
  if (!text || (last?.role === "user" && last.text === text)) return project;
  return {
    ...project,
    conversation: [
      ...project.conversation,
      { entry_id: `pending-${Date.now()}`, role: "user", type: "text", text, pending: true },
    ],
  };
}
