export type ProjectStatus = "needs_brief" | "ready_to_plan" | "awaiting_approval" | "running" | "needs_attention" | "ready";

export interface ProjectSummary { project_id: string; title: string; status: ProjectStatus; updated_at?: string }
export interface Material { name?: string; path: string; kind?: string; media_type?: string; mime?: string; size?: number }
export interface Artifact { artifact_id: string; path: string; name?: string; verified?: boolean; metadata?: { duration?: number; streams?: string[] } }
export interface Version { version_id: string; number?: number; parent_version_id?: string | null; change_note?: string; created_at?: string }
export interface Choice { value: string; label: string; recommended?: boolean }
export interface Question { question_id: string; text: string; choices?: Array<Choice | string>; blocking?: boolean }
export interface PlanStep { label?: string; tool?: string; description?: string }
export interface Plan { plan_id: string; summary?: string; status?: string; read_only?: boolean; steps?: PlanStep[]; stage_contract?: { human_approval_required?: boolean } }
export interface Operation { operation_id: string; project_id: string; plan_id?: string; status: string; progress_label?: string; current?: number; total?: number; can_resume?: boolean }
export interface ConversationEntry {
  entry_id?: string; role?: "user" | "assistant"; type: string; text?: string; summary?: string[]; active?: boolean;
  questions?: Question[]; question_set_id?: string; enhancements?: Array<{ enhancement_id: string; label: string; benefit?: string; cost?: string }>;
  plan?: Plan; artifact?: Artifact; artifact_bundle?: { artifact_id?: string; artifacts?: Artifact[] };
  label?: string; status?: string; step?: number; retained_work?: Artifact[];
}
export interface ProjectState extends ProjectSummary {
  project_root: string; projects: ProjectSummary[]; conversation: ConversationEntry[];
  input_manifest?: { inputs?: Material[] }; brief?: Record<string, unknown>; plan?: Plan | null;
  artifacts_state?: { expected?: unknown[]; verified?: Artifact[] }; verified_artifact?: Artifact | null;
  verified_artifacts?: Artifact[]; versions?: Version[]; operations?: Operation[];
}
export interface BootstrapPayload { projects: ProjectSummary[]; active_project: ProjectState }

export interface PyWebViewApi {
  bootstrap(): Promise<BootstrapPayload>;
  create_project(title: string): Promise<ProjectState>;
  open_project(projectId: string): Promise<ProjectState>;
  rename_project(projectId: string, title: string): Promise<ProjectState>;
  delete_project(projectId: string): Promise<{ deleted: { recoverable: boolean }; projects: ProjectSummary[]; active_project: ProjectState }>;
  pick_materials(projectId: string): Promise<{ materials: Material[]; project?: ProjectState }>;
  add_material_paths(projectId: string, paths: string[]): Promise<{ materials: Material[]; project?: ProjectState }>;
  submit(projectId: string, message: string, mode: string): Promise<ProjectState>;
  answer_questions(projectId: string, questionSetId: string, answers: Record<string, string>, mode: string): Promise<ProjectState>;
  set_enhancements(projectId: string, choices: Record<string, boolean>, mode: string): Promise<ProjectState>;
  approve_plan(projectId: string, planId: string, mode: string): Promise<{ operation: Operation; project: ProjectState }>;
  operation_status(operationId: string): Promise<{ operation: Operation; project: ProjectState }>;
  cancel_operation(operationId: string): Promise<Operation>;
  resume_operation(operationId: string): Promise<{ operation: Operation; project: ProjectState }>;
  create_version(projectId: string): Promise<ProjectState>;
  open_project_folder(projectId: string): Promise<{ ok: boolean; path: string }>;
  open_artifact(projectId: string, artifactId: string): Promise<{ ok: boolean; artifact: Artifact }>;
}

declare global {
  interface Window {
    pywebview?: { api: PyWebViewApi };
    addEventListener(type: "openmontage:native-drop", listener: (event: CustomEvent<string[]>) => void): void;
    removeEventListener(type: "openmontage:native-drop", listener: (event: CustomEvent<string[]>) => void): void;
  }
}
