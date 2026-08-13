import { useEffect, useRef, useState } from "react";
import { Group, Panel, Separator, usePanelRef } from "react-resizable-panels";
import { motion } from "motion/react";
import { ChevronsDown, ChevronsUp, FolderOpen, PanelLeft, PanelRight, Rows3, RotateCcw } from "lucide-react";
import type { Artifact, Operation, Plan, ProjectState, ProjectSummary } from "../types";
import { STAGES, statusCopy } from "../viewModel";
import { Inspector } from "./Inspector";
import { ProjectRail } from "./ProjectRail";
import { StudioStage } from "./StudioStage";
import { Timeline } from "./Timeline";

type Props = {
  project: ProjectState; projects: ProjectSummary[]; mode: string; disabled?: boolean; activity?: "command" | "answers"; error?: string;
  onMode: (mode: string) => void; onClearError: () => void; onCreate: () => void; onOpen: (id: string) => void;
  onRename: (title: string) => void; onDelete: () => void; onAdd: () => void; onSubmit: (message: string) => void;
  onDropPaths: (paths: string[]) => void;
  onQuestions: (id: string, answers: Record<string, string>) => void; onEnhancements: (choices: Record<string, boolean>) => void;
  onApprove: (plan: Plan) => void; onCancel: (operation: Operation) => void; onResume: (operation: Operation) => void;
  onOpenFolder: () => void; onOpenArtifact: (artifact: Artifact) => void; onVersion: () => void;
};

function useCompactWindow(limit = 1080) {
  const [compact, setCompact] = useState(() => window.innerWidth < limit);
  useEffect(() => { const update = () => setCompact(window.innerWidth < limit); window.addEventListener("resize", update); return () => window.removeEventListener("resize", update); }, [limit]);
  return compact;
}

export function Workspace(props: Props) {
  const compact = useCompactWindow();
  const leftRef = usePanelRef();
  const rightRef = usePanelRef();
  const timelineRef = usePanelRef();
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [timelineOpen, setTimelineOpen] = useState(true);
  const [sheet, setSheet] = useState<"projects" | "inspector" | null>(null);
  const status = statusCopy(props.project.status);
  const projectsVisible = compact ? sheet === "projects" : leftOpen;
  const inspectorVisible = compact ? sheet === "inspector" : rightOpen;

  const rail = (hidden = false) => <div className={`panel-content ${hidden ? "panel-content-hidden" : ""}`} aria-hidden={hidden || undefined}><ProjectRail active={props.project} projects={props.projects} disabled={props.disabled || hidden} onClose={compact ? () => setSheet(null) : () => { leftRef.current?.collapse(); setLeftOpen(false); }} onCreate={props.onCreate} onOpen={(id) => { props.onOpen(id); if (compact) setSheet(null); }} onRename={props.onRename} onDelete={props.onDelete} onOpenFolder={props.onOpenFolder}/></div>;
  const inspector = (hidden = false) => <div className={`panel-content ${hidden ? "panel-content-hidden" : ""}`} aria-hidden={hidden || undefined}><Inspector project={props.project} mode={props.mode} disabled={props.disabled || hidden} activity={props.activity} onClose={compact ? () => setSheet(null) : () => { rightRef.current?.collapse(); setRightOpen(false); }} onMode={props.onMode} onAdd={props.onAdd} onSubmit={props.onSubmit} onQuestions={props.onQuestions} onEnhancements={props.onEnhancements} onApprove={props.onApprove} onCancel={props.onCancel} onResume={props.onResume} onOpenFolder={props.onOpenFolder} onOpenArtifact={props.onOpenArtifact} onVersion={props.onVersion}/></div>;

  function resetLayout() {
    leftRef.current?.resize("18%"); rightRef.current?.resize("28%"); timelineRef.current?.resize("25%");
    setLeftOpen(true); setRightOpen(true); setTimelineOpen(true); setSheet(null);
  }

  return <main className={`workspace ${compact ? "compact-window" : ""}`}>
    <header className="topbar">
      <div className="topbar-left">
        <button className="icon-button" title={projectsVisible ? "Скрыть проекты" : "Показать проекты"} onClick={() => compact ? setSheet(sheet === "projects" ? null : "projects") : (leftOpen ? leftRef.current?.collapse() : leftRef.current?.expand(), setLeftOpen(!leftOpen))} aria-label={projectsVisible ? "Скрыть проекты" : "Показать проекты"} aria-expanded={projectsVisible}><PanelLeft/></button>
        <div className="project-heading"><h1>{props.project.title}</h1><button onClick={props.onOpenFolder}><FolderOpen/>{props.project.project_root}</button></div>
      </div>
      <div className="stage-meter" aria-label={`Этап ${status.stage} из ${STAGES.length}`}><span className="stage-copy">{status.label}</span><div>{STAGES.map((stage, index) => <i key={stage} className={index < status.stage ? "complete" : ""} title={stage}/>)}</div></div>
      <div className="topbar-actions">
        <button className="icon-button" title={timelineOpen ? "Скрыть обзор монтажа" : "Показать обзор монтажа"} onClick={() => timelineOpen ? timelineRef.current?.collapse() : timelineRef.current?.expand()} aria-label={timelineOpen ? "Скрыть обзор монтажа" : "Показать обзор монтажа"} aria-expanded={timelineOpen}>{timelineOpen ? <ChevronsDown/> : <ChevronsUp/>}</button>
        <button className="icon-button" title={inspectorVisible ? "Скрыть помощника" : "Показать помощника"} onClick={() => compact ? setSheet(sheet === "inspector" ? null : "inspector") : (rightOpen ? rightRef.current?.collapse() : rightRef.current?.expand(), setRightOpen(!rightOpen))} aria-label={inspectorVisible ? "Скрыть помощника" : "Показать помощника"} aria-expanded={inspectorVisible}><PanelRight/></button>
        <button className="icon-button" title="Сбросить расположение" onClick={resetLayout} aria-label="Сбросить расположение"><RotateCcw/></button>
      </div>
    </header>
    {props.error && <div className="inline-error" role="alert"><span>{props.error}</span><button onClick={props.onClearError}>Закрыть</button></div>}

    <div className="work-area">
      {compact ? <Center project={props.project} timelineRef={timelineRef} timelineOpen={timelineOpen} setTimelineOpen={setTimelineOpen} onAdd={props.onAdd} onDropPaths={props.onDropPaths} onOpenArtifact={props.onOpenArtifact}/>
        : <Group orientation="horizontal" id="openmontage-workspace" className="desktop-layout">
          <Panel id="projects" panelRef={leftRef} defaultSize="18%" minSize="220px" maxSize="360px" collapsible collapsedSize={0} onResize={(size) => setLeftOpen(size.inPixels > 0)}>{rail(!leftOpen)}</Panel>
          <Separator className="resize-handle vertical"><span/></Separator>
          <Panel id="stage" minSize="420px"><Center project={props.project} timelineRef={timelineRef} timelineOpen={timelineOpen} setTimelineOpen={setTimelineOpen} onAdd={props.onAdd} onDropPaths={props.onDropPaths} onOpenArtifact={props.onOpenArtifact}/></Panel>
          <Separator className="resize-handle vertical"><span/></Separator>
          <Panel id="inspector" panelRef={rightRef} defaultSize="28%" minSize="340px" maxSize="520px" collapsible collapsedSize={0} onResize={(size) => setRightOpen(size.inPixels > 0)}>{inspector(!rightOpen)}</Panel>
        </Group>}
    </div>
    {compact && sheet && <><motion.button className="sheet-scrim" aria-label="Закрыть панель" onClick={() => setSheet(null)} initial={{ opacity: 0 }} animate={{ opacity: 1 }}/><motion.div className={`mobile-sheet ${sheet}-sheet`} initial={{ x: sheet === "projects" ? -36 : 36, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ type: "spring", stiffness: 430, damping: 36 }}>{sheet === "projects" ? rail() : inspector()}</motion.div></>}
  </main>;
}

function Center({ project, timelineRef, timelineOpen, setTimelineOpen, onAdd, onDropPaths, onOpenArtifact }: { project: ProjectState; timelineRef: ReturnType<typeof usePanelRef>; timelineOpen: boolean; setTimelineOpen: (open: boolean) => void; onAdd: () => void; onDropPaths: (paths: string[]) => void; onOpenArtifact: (artifact: Artifact) => void }) {
  return <div className="center-workspace"><Group orientation="vertical" id="stage-timeline" className="center-panels">
    <Panel id="preview" minSize="260px"><StudioStage project={project} onAdd={onAdd} onDropPaths={onDropPaths} onOpenArtifact={onOpenArtifact}/></Panel>
    <Separator className="resize-handle horizontal"><span/><button onClick={() => timelineOpen ? timelineRef.current?.collapse() : timelineRef.current?.expand()} aria-label={timelineOpen ? "Скрыть обзор монтажа" : "Показать обзор монтажа"}><Rows3/></button></Separator>
    <Panel id="timeline" panelRef={timelineRef} defaultSize="25%" minSize="150px" maxSize="44%" collapsible collapsedSize={0} onResize={(size) => setTimelineOpen(size.inPixels > 0)}><Timeline project={project}/></Panel>
  </Group></div>;
}
