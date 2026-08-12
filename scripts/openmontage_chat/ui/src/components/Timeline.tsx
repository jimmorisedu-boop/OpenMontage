import { AudioLines, Film, GripHorizontal, MessageSquareText, Sparkles } from "lucide-react";
import type { ProjectState } from "../types";
import { playableArtifact, timecode } from "../viewModel";

export function Timeline({ project }: { project: ProjectState }) {
  const artifact = playableArtifact(project);
  const duration = artifact?.metadata?.duration || Math.max(15, (project.plan?.steps?.length || 1) * 15);
  const steps = project.plan?.steps || [];
  const materials = project.input_manifest?.inputs || [];
  const segments = steps.length ? steps.map((step, index) => ({ label: step.label || step.description || `Этап ${index + 1}`, tone: index % 4 })) : materials.slice(0, 8).map((item, index) => ({ label: item.name || `Исходник ${index + 1}`, tone: index % 4 }));

  return <section className="timeline" aria-label="Обзор монтажа">
    <header className="timeline-header"><div><GripHorizontal/><strong>Обзор монтажа</strong><span>формируется из плана</span></div><div className="timeline-zoom">{timecode(duration)}</div></header>
    <div className="timeline-body">
      <div className="time-ruler"><span>00:00</span><span>{timecode(duration / 2)}</span><span>{timecode(duration)}</span></div>
      <div className="playhead"/>
      <div className="track"><span className="track-name"><Film/>Видео</span><div className="segments">
        {segments.length ? segments.map((segment, index) => <div key={`${segment.label}-${index}`} className="timeline-segment" data-tone={segment.tone} style={{ flex: `${1 + (index % 3) * .3}` }}><span>{segment.label}</span></div>) : <div className="track-placeholder">Добавьте исходники</div>}
      </div></div>
      <div className="track"><span className="track-name"><AudioLines/>Звук</span><div className="audio-wave">{Array.from({ length: 54 }).map((_, index) => <i key={index} style={{ height: `${18 + ((index * 17) % 58)}%` }}/>)}</div></div>
      <div className="track compact"><span className="track-name"><MessageSquareText/>Титры</span><div className="caption-lane">{project.plan ? <span><Sparkles/>Будут собраны по утверждённому плану</span> : <span>Появятся после согласования задачи</span>}</div></div>
    </div>
  </section>;
}
