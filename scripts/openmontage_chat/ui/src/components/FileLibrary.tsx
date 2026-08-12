import { File, FileAudio, FileImage, FileText, Film, FolderOpen, History, Play, Plus } from "lucide-react";
import type { Artifact, Material, ProjectState } from "../types";
import { allArtifacts, bytes, groupMaterials } from "../viewModel";

const GROUP_COPY: Record<string, { label: string; icon: typeof Film }> = {
  video: { label: "Видео", icon: Film }, audio: { label: "Звук", icon: FileAudio },
  image: { label: "Изображения", icon: FileImage }, document: { label: "Документы", icon: FileText },
};

export function FileLibrary({ project, onAdd, onOpenFolder, onOpenArtifact, onVersion }: {
  project: ProjectState; onAdd: () => void; onOpenFolder: () => void; onOpenArtifact: (artifact: Artifact) => void; onVersion: () => void;
}) {
  const groups = groupMaterials(project.input_manifest?.inputs || []);
  const outputs = allArtifacts(project);
  const hasInputs = Object.values(groups).some((items) => items.length);
  return <div className="file-library">
    <div className="library-actions"><button className="button secondary compact" onClick={onAdd}><Plus/>Добавить</button><button className="button ghost compact" onClick={onOpenFolder}><FolderOpen/>Папка проекта</button></div>
    <LibrarySection title="Исходники" count={(project.input_manifest?.inputs || []).length}>
      {Object.entries(groups).map(([kind, items]) => items.length ? <MaterialGroup kind={kind} items={items} key={kind}/> : null)}
      {!hasInputs && <EmptyLibrary icon={File} text="Здесь появятся добавленные материалы"/>}
    </LibrarySection>
    <LibrarySection title="Результаты" count={outputs.length}>
      {outputs.map((artifact) => <button className="file-row actionable" key={artifact.artifact_id || artifact.path} onClick={() => onOpenArtifact(artifact)}><span className="file-icon result"><Play/></span><span><strong>{artifact.name || artifact.path.split(/[\\/]/).pop()}</strong><small>{artifact.verified ? "Проверен • " : ""}{artifact.metadata?.duration ? `${Math.round(artifact.metadata.duration)} сек.` : "Локальный файл"}</small></span></button>)}
      {!outputs.length && <EmptyLibrary icon={Play} text="Готовые монтажи появятся здесь"/>}
    </LibrarySection>
    <LibrarySection title="Версии" count={project.versions?.length || 0} action={<button className="text-action" onClick={onVersion}><Plus/>Новая версия</button>}>
      {(project.versions || []).slice().reverse().map((version) => <div className="file-row" key={version.version_id}><span className="file-icon"><History/></span><span><strong>Версия {version.number || version.version_id}</strong><small>{version.change_note || "Сохранённый этап"}{version.parent_version_id ? ` • из ${version.parent_version_id}` : ""}</small></span></div>)}
      {!project.versions?.length && <EmptyLibrary icon={History} text="Создайте версию перед крупной правкой"/>}
    </LibrarySection>
  </div>;
}

function LibrarySection({ title, count, action, children }: { title: string; count: number; action?: React.ReactNode; children: React.ReactNode }) {
  return <section className="library-section"><header><div><strong>{title}</strong><span>{count}</span></div>{action}</header><div className="library-content">{children}</div></section>;
}

function MaterialGroup({ kind, items }: { kind: string; items: Material[] }) {
  const copy = GROUP_COPY[kind] || GROUP_COPY.document;
  const Icon = copy.icon;
  return <div className="material-group"><div className="material-group-title"><Icon/>{copy.label}<span>{items.length}</span></div>{items.map((item) => <div className="file-row" key={item.path}><span className="file-icon"><Icon/></span><span title={item.path}><strong>{item.name || item.path.split(/[\\/]/).pop()}</strong><small>{bytes(item.size) || "Локальный файл"}</small></span></div>)}</div>;
}

function EmptyLibrary({ icon: Icon, text }: { icon: typeof File; text: string }) {
  return <div className="library-empty"><Icon/><span>{text}</span></div>;
}
