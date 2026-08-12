import { useEffect, useState } from "react";
import { AlertDialog, DropdownMenu, Tooltip } from "radix-ui";
import { Clapperboard, FolderOpen, MoreHorizontal, PanelLeftClose, Pencil, Plus, Search, Trash2 } from "lucide-react";
import type { ProjectState, ProjectSummary } from "../types";
import { statusCopy } from "../viewModel";

type Props = {
  active: ProjectState;
  projects: ProjectSummary[];
  disabled?: boolean;
  onClose?: () => void;
  onCreate: () => void;
  onOpen: (id: string) => void;
  onRename: (title: string) => void;
  onDelete: () => void;
  onOpenFolder: () => void;
};

export function ProjectRail({ active, projects, disabled, onClose, onCreate, onOpen, onRename, onDelete, onOpenFolder }: Props) {
  const [query, setQuery] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState(active.title);
  useEffect(() => setTitle(active.title), [active.project_id, active.title]);
  const filtered = projects.filter((item) => item.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()));

  function saveRename() {
    const clean = title.trim();
    if (clean && clean !== active.title) onRename(clean);
    setRenaming(false);
  }

  return <aside className="project-rail" aria-label="Проекты">
    <div className="brand-row">
      <div className="brand-mark" aria-hidden="true"><Clapperboard size={18}/></div>
      <div className="brand-copy"><strong>OpenMontage</strong><span>Локальная монтажная</span></div>
      {onClose && <Tooltip.Root><Tooltip.Trigger asChild><button className="icon-button subtle" onClick={onClose} aria-label="Скрыть проекты"><PanelLeftClose/></button></Tooltip.Trigger><Tooltip.Portal><Tooltip.Content className="tooltip" side="bottom">Скрыть проекты</Tooltip.Content></Tooltip.Portal></Tooltip.Root>}
    </div>

    <button className="new-project" onClick={onCreate} disabled={disabled}><Plus/>Новый монтаж</button>
    <label className="search-field"><Search/><span className="sr-only">Найти проект</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти проект"/></label>

    <div className="rail-heading"><span>Проекты</span><span>{filtered.length}</span></div>
    <nav className="project-list" aria-label="Список проектов">
      {filtered.map((project) => {
        const status = statusCopy(project.status);
        const isActive = project.project_id === active.project_id;
        return <div className={`project-row ${isActive ? "active" : ""}`} key={project.project_id}>
          <button className="project-main" onClick={() => onOpen(project.project_id)} disabled={disabled} aria-current={isActive ? "page" : undefined}>
            <span className="project-title">{project.title}</span>
            <span className="project-meta"><i data-tone={status.tone}/>{status.label}</span>
          </button>
          {isActive && <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild><button className="project-more" aria-label="Действия с проектом"><MoreHorizontal/></button></DropdownMenu.Trigger>
            <DropdownMenu.Portal><DropdownMenu.Content className="menu" sideOffset={7} align="end">
              <DropdownMenu.Item className="menu-item" onSelect={() => setRenaming(true)}><Pencil/>Переименовать</DropdownMenu.Item>
              <DropdownMenu.Item className="menu-item" onSelect={onOpenFolder}><FolderOpen/>Открыть папку</DropdownMenu.Item>
              <AlertDialog.Root><AlertDialog.Trigger asChild><DropdownMenu.Item className="menu-item danger" onSelect={(event) => event.preventDefault()}><Trash2/>Удалить</DropdownMenu.Item></AlertDialog.Trigger>
                <AlertDialog.Portal><AlertDialog.Overlay className="dialog-overlay"/><AlertDialog.Content className="dialog-card">
                  <AlertDialog.Title>Удалить «{active.title}»?</AlertDialog.Title>
                  <AlertDialog.Description>Проект будет перемещён в локальную корзину OpenMontage. Его материалы на диске останутся восстанавливаемыми.</AlertDialog.Description>
                  <div className="dialog-actions"><AlertDialog.Cancel asChild><button className="button secondary">Отмена</button></AlertDialog.Cancel><AlertDialog.Action asChild><button className="button danger" onClick={onDelete}>Удалить проект</button></AlertDialog.Action></div>
                </AlertDialog.Content></AlertDialog.Portal>
              </AlertDialog.Root>
            </DropdownMenu.Content></DropdownMenu.Portal>
          </DropdownMenu.Root>}
        </div>;
      })}
      {!filtered.length && <div className="rail-empty">Проекты не найдены</div>}
    </nav>

    <div className="rail-footer"><span className="local-dot"/>Всё остаётся на этом компьютере</div>

    {renaming && <div className="dialog-overlay manual"><form className="dialog-card" onSubmit={(event) => { event.preventDefault(); saveRename(); }}>
      <h2>Название проекта</h2><p>Короткое название легче найти в списке и в папке монтажей.</p>
      <label className="field-label">Название<input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} maxLength={80}/></label>
      <div className="dialog-actions"><button type="button" className="button secondary" onClick={() => setRenaming(false)}>Отмена</button><button className="button primary" disabled={!title.trim()}>Сохранить</button></div>
    </form></div>}
  </aside>;
}
