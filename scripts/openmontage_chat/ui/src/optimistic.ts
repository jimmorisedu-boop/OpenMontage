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

export function withOptimisticAnswers(project: ProjectState, questionSetId: string): ProjectState {
  return {
    ...project,
    conversation: project.conversation.map((entry) =>
      entry.type === "questions" && entry.question_set_id === questionSetId
        ? { ...entry, active: false, pending: true }
        : entry,
    ),
  };
}
