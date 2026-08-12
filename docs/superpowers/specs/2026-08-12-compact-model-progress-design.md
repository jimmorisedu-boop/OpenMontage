# Compact Model Progress

## Goal

Make OpenMontage feel active during longer local-model operations without exposing private chain-of-thought or flooding the chat with transient messages.

## User experience

- While a request is running, the composer shows one compact progress line.
- The line advances through a small fixed vocabulary such as `Изучаю материалы`, `Собираю структуру`, and `Готовлю ответ`.
- Each new state replaces the previous state. Progress states are never appended as chat messages.
- The interface does not invent percentage completion or elapsed-time promises.
- When the response arrives, the transient progress line returns to the normal local-processing label.
- An assistant response may include a collapsed `Как я подошёл к задаче` section containing two to four concise, user-useful conclusions.
- Raw chain-of-thought, hidden prompts, tokens, provider details, stack traces, and model logs are never displayed.
- Errors and confirmation requests remain ordinary, clearly visible assistant messages.

## Data contract

The desktop bridge returns:

```json
{
  "answer": "User-facing answer",
  "summary": ["Short conclusion", "Short conclusion"]
}
```

`summary` is optional. The backend accepts only a list of short strings, trims it to four entries, and discards empty entries. Existing model responses that return only `answer` remain valid.

The local model is instructed to place its final response and a concise approach summary in a bounded machine-readable format. If parsing fails, OpenMontage presents the full text as `answer` and omits the summary; a formatting issue must not lose the answer.

## Interface components

1. `ProgressStatus` is the existing single composer status element, updated in place by a timer while a request is pending.
2. `ApproachSummary` is a native HTML `details` element inside the assistant message. It is collapsed by default and is rendered only when sanitized summary items exist.
3. The normal answer stays visually primary. The summary uses smaller muted text and does not interrupt reading.

## State and failure handling

- Only one request can be active because the send button is disabled until completion.
- The progress timer is always stopped in `finally`, on both success and failure.
- Starting a new chat clears messages and any visible transient state.
- If the bridge throws, the error appears once as an assistant message and the composer returns to its idle label.
- Model output is inserted with DOM text nodes, not `innerHTML`, so generated text cannot inject markup.

## Verification

- Backend tests cover valid summaries, empty or oversized summaries, and fallback for unstructured model output.
- shell-contract tests cover the single replace-in-place progress element, collapsed summary control, lack of raw reasoning labels, and absence of HTTP `fetch`.
- Existing fixed-model, material-picker, launcher, and full repository tests must remain green.

## Out of scope

- Token-by-token chain-of-thought streaming.
- Detailed logs in the conversation.
- Progress percentages that cannot be measured reliably.
- Model, provider, or agent selection controls.
