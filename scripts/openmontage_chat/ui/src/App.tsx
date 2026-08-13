import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MotionConfig } from "motion/react";
import { Tooltip } from "radix-ui";
import type { Artifact, Operation, Plan, ProjectState, ProjectSummary, PyWebViewApi } from "./types";
import { waitForBridge } from "./bridge";
import { withOptimisticCommand } from "./optimistic";
import { Workspace } from "./components/Workspace";

export function App() {
  const [api, setApi] = useState<PyWebViewApi | null>(null);
  const [project, setProject] = useState<ProjectState | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [mode, setMode] = useState(readSavedMode);
  const [pending, setPending] = useState(0);
  const [pendingCommand, setPendingCommand] = useState("");
  const [error, setError] = useState("");
  const mounted = useRef(true);

  const applyProject = useCallback((value: ProjectState) => {
    if (!mounted.current) return;
    setProject(value); setProjects(value.projects || []);
  }, []);

  useEffect(() => {
    mounted.current = true;
    waitForBridge().then(async (bridge) => {
      setApi(bridge);
      try { const payload = await bridge.bootstrap(); if (mounted.current) { setProject(payload.active_project); setProjects(payload.projects); } }
      catch (reason) { setError(errorMessage(reason)); }
    });
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => { try { localStorage.setItem("openmontage-mode", mode); } catch { /* html-string WebView can deny storage */ } }, [mode]);

  const activeOperation = useMemo(() => (project?.operations || []).find((item) => ["queued", "running", "cancelling"].includes(item.status)), [project?.operations]);
  useEffect(() => {
    if (!api || !activeOperation) return;
    const timer = window.setTimeout(async () => {
      try { const response = await api.operation_status(activeOperation.operation_id); applyProject(response.project); }
      catch (reason) { setError(errorMessage(reason)); }
    }, 900);
    return () => window.clearTimeout(timer);
  }, [api, activeOperation?.operation_id, activeOperation?.status, activeOperation?.current, applyProject]);

  const run = useCallback(async <T,>(action: () => Promise<T>, apply?: (value: T) => void) => {
    setPending((value) => value + 1); setError("");
    try { const value = await action(); if (mounted.current) apply?.(value); return value; }
    catch (reason) { if (mounted.current) setError(errorMessage(reason)); return undefined; }
    finally { if (mounted.current) setPending((value) => Math.max(0, value - 1)); }
  }, []);

  if (!project || !api) return <div className="launch-screen"><div className="launch-mark">OM</div><strong>OpenMontage</strong><span>Открываю локальную монтажную…</span></div>;

  const activeId = project.project_id;
  const visibleProject = pendingCommand ? withOptimisticCommand(project, pendingCommand) : project;
  return <Tooltip.Provider delayDuration={450}><MotionConfig reducedMotion="user"><Workspace project={visibleProject} projects={projects} mode={mode} disabled={pending > 0} thinking={Boolean(pendingCommand)} error={error} onClearError={() => setError("")} onMode={setMode}
    onCreate={() => run(() => api.create_project("Новый монтаж"), applyProject)}
    onOpen={(id) => run(() => api.open_project(id), applyProject)}
    onRename={(title) => run(() => api.rename_project(activeId, title), applyProject)}
    onDelete={() => run(() => api.delete_project(activeId), (response) => { setProjects(response.projects); applyProject(response.active_project); })}
    onAdd={() => run(() => api.pick_materials(activeId), (response) => { if (response.project) applyProject(response.project); })}
    onDropPaths={(paths) => run(() => api.add_material_paths(activeId, paths), (response) => { if (response.project) applyProject(response.project); })}
    onSubmit={(message) => {
      setPendingCommand(message);
      void run(() => api.submit(activeId, message, mode), applyProject).then(async (result) => {
        if (!result) { const saved = await api.open_project(activeId); applyProject(saved); }
      }).finally(() => { if (mounted.current) setPendingCommand(""); });
    }}
    onQuestions={(id, answers) => run(() => api.answer_questions(activeId, id, answers, mode), applyProject)}
    onEnhancements={(choices) => run(() => api.set_enhancements(activeId, choices, mode), applyProject)}
    onApprove={(plan: Plan) => run(() => api.approve_plan(activeId, plan.plan_id, mode), (response) => applyProject(response.project))}
    onCancel={(operation: Operation) => run(() => api.cancel_operation(operation.operation_id), () => api.operation_status(operation.operation_id).then((response) => applyProject(response.project)))}
    onResume={(operation: Operation) => run(() => api.resume_operation(operation.operation_id), (response) => applyProject(response.project))}
    onOpenFolder={() => run(() => api.open_project_folder(activeId))}
    onOpenArtifact={(artifact: Artifact) => run(() => api.open_artifact(activeId, artifact.artifact_id || artifact.path))}
    onVersion={() => run(() => api.create_version(activeId), applyProject)}
  /></MotionConfig></Tooltip.Provider>;
}

function errorMessage(reason: unknown) {
  const raw = reason instanceof Error ? reason.message : String(reason || "Неизвестная ошибка");
  return raw.replace(/^Error:\s*/i, "").replace(/^.*?\b(?:RuntimeError|ValueError|PermissionError):\s*/i, "") || "Не удалось выполнить действие";
}

function readSavedMode() {
  try { return localStorage.getItem("openmontage-mode") || "confirm"; }
  catch { return "confirm"; }
}
