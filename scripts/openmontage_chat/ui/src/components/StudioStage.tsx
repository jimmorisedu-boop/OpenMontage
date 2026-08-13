import { type DragEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CirclePlay, ExternalLink, Film, FolderPlus, ImageIcon, Music2, Sparkles } from "lucide-react";
import type { Artifact, ProjectState } from "../types";
import { fileUrl, playableArtifact, statusCopy } from "../viewModel";

type Props = { project: ProjectState; onAdd: () => void; onDropPaths: (paths: string[]) => void; onOpenArtifact: (artifact: Artifact) => void };

export function StudioStage({ project, onAdd, onDropPaths, onOpenArtifact }: Props) {
  const artifact = playableArtifact(project);
  const [previewFailed, setPreviewFailed] = useState(false);
  const status = statusCopy(project.status);
  const materials = project.input_manifest?.inputs || [];
  const counts = materials.reduce<Record<string, number>>((memo, item) => { memo[item.kind || "document"] = (memo[item.kind || "document"] || 0) + 1; return memo; }, {});

  return <DropZone onBrowse={onAdd} onDropPaths={onDropPaths}><section className="studio-stage" aria-label="Предпросмотр монтажа">
    <AnimatePresence mode="wait">
      {artifact && !previewFailed ? <motion.div className="preview-frame" key={artifact.artifact_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
        <video className="preview-video" controls src={fileUrl(artifact.path)} onError={() => setPreviewFailed(true)}/>
        <div className="preview-caption"><span className="live-pill"><i/>Проверенный результат</span><button className="glass-button" onClick={() => onOpenArtifact(artifact)}><ExternalLink/>Открыть файл</button></div>
      </motion.div> : <motion.div className="empty-stage" key="empty" initial={{ opacity: 0, scale: .99 }} animate={{ opacity: 1, scale: 1 }}>
        <div className="stage-glow"/>
        <div className="empty-visual"><div className="frame-lines"/><CirclePlay/></div>
        {previewFailed ? <><p className="eyebrow danger-text">Предпросмотр недоступен</p><h2>Файл готов на диске</h2><p>Встроенный проигрыватель не распознал формат. Откройте проверенный результат системным плеером.</p><button className="button primary" onClick={() => artifact && onOpenArtifact(artifact)}><ExternalLink/>Открыть результат</button></>
          : <><p className="eyebrow">{status.label}</p><h2>{materials.length ? "Готово к режиссёрской задаче" : "Начните с исходников"}</h2><p>{materials.length ? "Опишите, каким должен стать материал. Помощник уточнит только то, без чего нельзя принять хорошее монтажное решение." : "Добавьте видео, звук, сценарий, раскадровку или любые пояснения. OpenMontage разберёт их локально."}</p><button className="button primary" onClick={onAdd}><FolderPlus/>Добавить материалы</button></>}
        {!!materials.length && <div className="material-summary" aria-label="Добавленные материалы">
          {!!counts.video && <span><Film/>{counts.video} видео</span>}
          {!!counts.audio && <span><Music2/>{counts.audio} аудио</span>}
          {!!counts.image && <span><ImageIcon/>{counts.image} изображ.</span>}
          {!!counts.document && <span><Sparkles/>{counts.document} докум.</span>}
        </div>}
      </motion.div>}
    </AnimatePresence>
  </section></DropZone>;
}

function DropZone({ children, onDropPaths }: { children: ReactNode; onBrowse: () => void; onDropPaths: (paths: string[]) => void }) {
  const [dragging, setDragging] = useState(false);
  const depth = useRef(0);

  useEffect(() => {
    const receive = (event: CustomEvent<string[]>) => {
      depth.current = 0;
      setDragging(false);
      if (event.detail.length) onDropPaths(event.detail);
    };
    window.addEventListener("openmontage:native-drop", receive);
    return () => window.removeEventListener("openmontage:native-drop", receive);
  }, [onDropPaths]);

  const enter = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    depth.current += 1;
    setDragging(true);
  };
  const leave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    depth.current = Math.max(0, depth.current - 1);
    if (!depth.current) setDragging(false);
  };
  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    depth.current = 0;
    setDragging(false);
    const paths = Array.from(event.dataTransfer.files)
      .map((file) => (file as File & { pywebviewFullPath?: string }).pywebviewFullPath)
      .filter((path): path is string => Boolean(path));
    if (paths.length) onDropPaths(paths);
  };
  return <div className={`drop-zone ${dragging ? "is-dragging" : ""}`} role="region" aria-label="Зона добавления материалов" onDragEnter={enter} onDragOver={(event) => event.preventDefault()} onDragLeave={leave} onDrop={drop}>
    {children}
    {dragging && <div className="drop-overlay" aria-live="polite"><FolderPlus/><strong>Перетащите материалы сюда</strong><span>Видео, звук, изображения и документы</span></div>}
  </div>;
}
