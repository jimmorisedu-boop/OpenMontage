import { useState } from "react";
import { Tabs, Tooltip } from "radix-ui";
import { ArrowUp, Bot, FolderPlus, Library, PanelRightClose, Paperclip } from "lucide-react";
import type { Artifact, Operation, Plan, ProjectState } from "../types";
import { Conversation } from "./Conversation";
import { FileLibrary } from "./FileLibrary";

type Props = {
  project: ProjectState; mode: string; disabled?: boolean; activity?: "command" | "answers"; onClose?: () => void;
  onMode: (mode: string) => void; onAdd: () => void; onSubmit: (message: string) => void;
  onQuestions: (id: string, answers: Record<string, string>) => void; onEnhancements: (choices: Record<string, boolean>) => void;
  onApprove: (plan: Plan) => void; onCancel: (operation: Operation) => void; onResume: (operation: Operation) => void;
  onOpenFolder: () => void; onOpenArtifact: (artifact: Artifact) => void; onVersion: () => void;
};

export function Inspector(props: Props) {
  const [tab, setTab] = useState("assistant");
  const [message, setMessage] = useState("");
  const canSend = Boolean(message.trim()) && !props.disabled;
  function submit() { if (!canSend) return; props.onSubmit(message.trim()); setMessage(""); }
  return <aside className="inspector" aria-label="Помощник и файлы">
    <header className="inspector-header"><Tabs.Root value={tab} onValueChange={setTab}><Tabs.List className="context-tabs" aria-label="Раздел инспектора"><Tabs.Trigger value="assistant"><Bot/>Помощник</Tabs.Trigger><Tabs.Trigger value="files"><Library/>Файлы<span>{(props.project.input_manifest?.inputs || []).length}</span></Tabs.Trigger></Tabs.List></Tabs.Root>
      {props.onClose && <Tooltip.Root><Tooltip.Trigger asChild><button className="icon-button subtle" onClick={props.onClose} aria-label="Скрыть помощника"><PanelRightClose/></button></Tooltip.Trigger><Tooltip.Portal><Tooltip.Content className="tooltip" side="bottom">Скрыть помощника</Tooltip.Content></Tooltip.Portal></Tooltip.Root>}
    </header>
    <div className="inspector-body">
      {tab === "assistant" ? <Conversation project={props.project} disabled={props.disabled} activity={props.activity} actions={{ answerQuestions: props.onQuestions, setEnhancements: props.onEnhancements, approvePlan: props.onApprove, cancelOperation: props.onCancel, resumeOperation: props.onResume, openArtifact: props.onOpenArtifact, createVersion: props.onVersion }}/>
        : <FileLibrary project={props.project} onAdd={props.onAdd} onOpenFolder={props.onOpenFolder} onOpenArtifact={props.onOpenArtifact} onVersion={props.onVersion}/>}
    </div>
    {tab === "assistant" && <div className="composer-wrap"><div className="composer"><textarea id="prompt" aria-label="Задача или правка" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder={props.project.conversation.length ? "Попросите изменить монтаж…" : "Опишите желаемый результат…"} rows={2}/><div className="composer-tools"><button className="attach-button" onClick={props.onAdd}><Paperclip/>Материалы</button><label className="mode-control"><span className="sr-only">Режим работы</span><select value={props.mode} onChange={(event) => props.onMode(event.target.value)} aria-label="Режим работы"><option value="confirm">С подтверждением</option><option value="auto">Автономно</option><option value="read_only">Только план</option></select></label><button className="send-button" onClick={submit} disabled={!canSend} aria-label="Отправить"><ArrowUp/></button></div></div><div className="composer-status"><span className={`local-dot ${props.activity ? "busy" : ""}`}/>{props.activity === "answers" ? "Учитываю ответы" : props.activity === "command" ? "Анализирую задачу" : "Готов к работе"}</div></div>}
  </aside>;
}
