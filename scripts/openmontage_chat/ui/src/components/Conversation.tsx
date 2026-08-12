import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { Check, CheckCircle2, ChevronDown, CircleAlert, CircleStop, Clock3, ExternalLink, Film, Lightbulb, ListChecks, LoaderCircle, Play, RotateCcw, Sparkles, WandSparkles } from "lucide-react";
import type { Artifact, Choice, ConversationEntry, Operation, Plan, ProjectState, Question } from "../types";
import { operationProgress } from "../viewModel";

type Actions = {
  answerQuestions: (questionSetId: string, answers: Record<string, string>) => void;
  setEnhancements: (choices: Record<string, boolean>) => void;
  approvePlan: (plan: Plan) => void;
  cancelOperation: (operation: Operation) => void;
  resumeOperation: (operation: Operation) => void;
  openArtifact: (artifact: Artifact) => void;
  createVersion: () => void;
};

export function Conversation({ project, actions, disabled }: { project: ProjectState; actions: Actions; disabled?: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  const entries = project.conversation || [];
  const currentOperation = useMemo(() => (project.operations || []).slice().reverse().find((item) => ["queued", "running", "cancelling", "cancelled", "failed"].includes(item.status)), [project.operations]);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [entries.length, currentOperation?.status]);
  return <div className="conversation" aria-live="polite" aria-busy={disabled}>
    {currentOperation && <OperationCard operation={currentOperation} onCancel={actions.cancelOperation} onResume={actions.resumeOperation}/>}
    {!entries.length && <WelcomeCard/>}
    {entries.map((entry, index) => <ConversationEntryView key={entry.entry_id || index} entry={entry} actions={actions}/>) }
    <div ref={endRef}/>
  </div>;
}

function WelcomeCard() {
  return <div className="welcome-card"><div className="assistant-avatar"><WandSparkles/></div><div><p className="eyebrow">Режиссёрский помощник</p><h3>Сначала — желаемый результат</h3><p>Напишите, что должно получиться. Я изучу все материалы, задам до трёх коротких вопросов только при необходимости и предложу понятный план.</p><div className="suggestion-list"><span><Check/>учту сценарий и пояснения</span><span><Check/>подберу локальные инструменты</span><span><Check/>покажу результат и путь к файлу</span></div></div></div>;
}

function ConversationEntryView({ entry, actions }: { entry: ConversationEntry; actions: Actions }) {
  if (entry.type === "questions" && entry.questions && entry.question_set_id) return <QuestionCard entry={entry} onSubmit={actions.answerQuestions}/>;
  if (entry.type === "enhancements" && entry.enhancements) return <EnhancementCard entry={entry} onSubmit={actions.setEnhancements}/>;
  if (entry.type === "plan" && entry.plan) return <PlanCard entry={entry} onApprove={actions.approvePlan}/>;
  if (entry.type === "result" && entry.artifact) return <ResultCard artifact={entry.artifact} onOpen={actions.openArtifact} onVersion={actions.createVersion}/>;
  if (entry.type === "blocker") return <div className="workflow-card blocker-card"><div className="card-icon danger"><CircleAlert/></div><div><p className="eyebrow">Нужно внимание</p><h3>{entry.text || "Операция остановлена"}</h3>{entry.retained_work?.length ? <p>Уже готовые материалы сохранены — работу можно продолжить после исправления.</p> : null}</div></div>;
  if (entry.type === "operation") return null;
  return <motion.article className={`message ${entry.role === "user" ? "user" : "assistant"}`} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}>
    {entry.role !== "user" && <div className="assistant-avatar small"><WandSparkles/></div>}
    <div className="message-body"><p>{entry.text}</p>{entry.summary?.length ? <details className="approach"><summary><Sparkles/>Как я подошёл к задаче<ChevronDown/></summary><ul>{entry.summary.map((item, index) => <li key={index}>{item}</li>)}</ul></details> : null}</div>
  </motion.article>;
}

function QuestionCard({ entry, onSubmit }: { entry: ConversationEntry; onSubmit: (id: string, answers: Record<string, string>) => void }) {
  const questions = (entry.questions || []).slice(0, 3);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const ready = questions.every((question) => !question.blocking || Boolean(answers[question.question_id]?.trim()));
  return <section className={`workflow-card question-card ${entry.active === false ? "resolved" : ""}`}>
    <header className="workflow-title"><div className="card-icon attention"><Lightbulb/></div><div><p className="eyebrow">Нужно уточнить</p><h3>{questions.length === 1 ? "Один короткий вопрос" : `${questions.length} коротких вопроса`}</h3></div>{entry.active === false && <span className="resolved-label"><CheckCircle2/>Отвечено</span>}</header>
    {questions.map((question, index) => <QuestionField key={question.question_id} question={question} number={index + 1} value={answers[question.question_id] || ""} disabled={entry.active === false} onChange={(value) => setAnswers((state) => ({ ...state, [question.question_id]: value }))}/>)}
    {entry.active !== false && <button className="button primary full" disabled={!ready} onClick={() => onSubmit(entry.question_set_id!, answers)}>Продолжить<Check/></button>}
  </section>;
}

function QuestionField({ question, number, value, disabled, onChange }: { question: Question; number: number; value: string; disabled: boolean; onChange: (value: string) => void }) {
  const [custom, setCustom] = useState(false);
  const choices = (question.choices || []).map((choice) => typeof choice === "string" ? { value: choice, label: choice } : choice) as Choice[];
  return <fieldset className="question-field" disabled={disabled}><legend><span>{number}</span>{question.text}</legend>
    <div className="choice-grid">{choices.map((choice) => <label className={`choice ${value === choice.value && !custom ? "selected" : ""}`} key={choice.value}><input type="radio" name={question.question_id} checked={value === choice.value && !custom} onChange={() => { setCustom(false); onChange(choice.value); }}/><span>{choice.label}{choice.recommended && <small>Рекомендуем</small>}</span><i><Check/></i></label>)}
      <label className={`choice ${custom ? "selected" : ""}`}><input type="radio" name={question.question_id} checked={custom} onChange={() => { setCustom(true); onChange(""); }}/><span>Другой ответ</span><i><Check/></i></label></div>
    {custom && <input className="custom-answer" autoFocus placeholder="Короткий ответ" value={value} onChange={(event) => onChange(event.target.value)}/>}
  </fieldset>;
}

function EnhancementCard({ entry, onSubmit }: { entry: ConversationEntry; onSubmit: (choices: Record<string, boolean>) => void }) {
  const [choices, setChoices] = useState<Record<string, boolean>>({});
  return <section className={`workflow-card enhancement-card ${entry.active === false ? "resolved" : ""}`}><header className="workflow-title"><div className="card-icon active"><Sparkles/></div><div><p className="eyebrow">Можно сделать лучше</p><h3>Дополнительные улучшения</h3></div></header>
    <div className="enhancement-list">{entry.enhancements?.map((item) => <label className="enhancement" key={item.enhancement_id}><input type="checkbox" disabled={entry.active === false} checked={!!choices[item.enhancement_id]} onChange={(event) => setChoices((state) => ({ ...state, [item.enhancement_id]: event.target.checked }))}/><span className="check-box"><Check/></span><span><strong>{item.label}</strong><small>{item.benefit}{item.cost ? ` • ${item.cost}` : ""}</small></span></label>)}</div>
    {entry.active !== false && <div className="card-actions"><button className="button secondary" onClick={() => onSubmit({})}>Пропустить</button><button className="button primary" onClick={() => onSubmit(choices)}>Применить выбранное</button></div>}
  </section>;
}

function PlanCard({ entry, onApprove }: { entry: ConversationEntry; onApprove: (plan: Plan) => void }) {
  const plan = entry.plan!;
  return <section className={`workflow-card plan-card ${entry.active === false ? "resolved" : ""}`}><header className="workflow-title"><div className="card-icon success"><ListChecks/></div><div><p className="eyebrow">План монтажа</p><h3>{plan.summary || "Готов к запуску"}</h3></div>{entry.active === false && <span className="resolved-label"><CheckCircle2/>Принят</span>}</header>
    <ol className="plan-steps">{(plan.steps || []).map((step, index) => <li key={index}><span>{index + 1}</span><div><strong>{step.label || step.tool || `Шаг ${index + 1}`}</strong>{step.description && <small>{step.description}</small>}</div></li>)}</ol>
    {entry.active !== false && !plan.read_only && <button className="button primary full" onClick={() => onApprove(plan)}><Play/>Подтвердить и запустить</button>}
    {plan.read_only && <div className="read-only-note"><CircleAlert/>Режим просмотра: запуск отключён</div>}
  </section>;
}

function ResultCard({ artifact, onOpen, onVersion }: { artifact: Artifact; onOpen: (artifact: Artifact) => void; onVersion: () => void }) {
  return <section className="workflow-card result-card"><header className="workflow-title"><div className="card-icon success"><Film/></div><div><p className="eyebrow">Результат готов</p><h3>{artifact.name || "Проверенный монтаж"}</h3><p className="artifact-path" title={artifact.path}>{artifact.path}</p></div><span className="verified"><CheckCircle2/>Проверен</span></header><div className="card-actions"><button className="button primary" onClick={() => onOpen(artifact)}><ExternalLink/>Смотреть</button><button className="button secondary" onClick={onVersion}><RotateCcw/>Новая версия</button></div></section>;
}

function OperationCard({ operation, onCancel, onResume }: { operation: Operation; onCancel: (operation: Operation) => void; onResume: (operation: Operation) => void }) {
  const active = ["queued", "running", "cancelling"].includes(operation.status);
  const progress = operationProgress(operation.current, operation.total);
  return <section className={`operation-card ${active ? "active" : ""}`}><div className="operation-heading"><span className="operation-icon">{active ? <LoaderCircle className="spin"/> : operation.status === "failed" ? <CircleAlert/> : <Clock3/>}</span><div><strong>{operation.progress_label || (active ? "Выполняю монтаж" : "Операция остановлена")}</strong><small>{operation.total ? `Шаг ${operation.current || 0} из ${operation.total}` : active ? "Подготавливаю локальные инструменты" : "Можно продолжить с сохранённого места"}</small></div><span>{progress}%</span></div><div className="progress-track"><motion.i animate={{ width: `${progress}%` }}/></div><div className="operation-actions">{active && operation.status !== "cancelling" && <button className="text-action danger" onClick={() => onCancel(operation)}><CircleStop/>Остановить</button>}{!active && operation.can_resume && <button className="text-action" onClick={() => onResume(operation)}><RotateCcw/>Продолжить</button>}</div></section>;
}
