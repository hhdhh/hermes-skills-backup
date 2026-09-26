---
name: hermes-meta-questions
description: Use when the user asks how Hermes/this agent works intern...
---

# Answering Meta-Questions About Hermes With Evidence

> 完整描述：Use when the user asks how Hermes/this agent works internally — "how do you find me", "how did you send that message", "how does auth work", "who can see this", "why did you do X", or any meta question about message routing, identity, platform permissions, or agent behavior. Answer from logs (gateway/agent/platform logs) and config, never from "general chatbot knowledge." User has demonstrated they reject plausible-sounding answers without evidence.

## The rule (always)

When the user asks **how this agent works**, **how it does X**, **why it can do Y**, or **how it found them** — answer from **concrete evidence in the local logs and config**, not from "what I know about chatbots in general."

The user will ask follow-ups until you show the actual log line, config field, or API call. **Plausible-sounding answers are a worse failure than "I don't know, let me check"** — they have already caught the agent fabricating facts about its own behavior and will keep testing.

## Procedure

1. **Classify the question** into one of:
   - **Identity / routing** — "how do you find me", "how do you know who I am", "how does this work in a DM vs group"
   - **Permissions / scoping** — "users have to apply, right?", "who can see this app", "why can you message me"
   - **Internal mechanism** — "how did you send that", "why was that response delayed", "how did the tool call route"
   - **Counterfactual / claim-check** — "is it true that…", "didn't you just…"

2. **For each, identify the authoritative source** before answering:
   - Identity / routing → `~/.hermes/logs/agent.log` for the relevant platform's `[Feishu]/[Telegram]/[Discord]` lines, especially `Inbound dm message received` (carries `sender.open_id` + `chat_id`) and `Sending response` (carries the `chat_id` it replied to)
   - Permissions / scoping → the platform's admin console for the app, plus `~/.hermes/config.yaml` for `messaging.*` settings
   - Internal mechanism → `~/.hermes/logs/gateway.log` for the recent session id (e.g. `20260915_114700_32dde0ac`) and trace all `inbound` / `outbound` / `tool call` events for it
   - Counterfactual → the **same** logs filtered for the timestamp window the user mentions; never infer from prior turns

3. **Run the grep / search first**, then compose the answer. The shape of the answer is a small **timeline of evidence**:
   - timestamp + log line + what it proves
   - one paragraph explaining the chain
   - a **"what I got wrong"** note if any prior turn claimed something the evidence now contradicts

4. **If the evidence contradicts what you said earlier in the same session**, say so explicitly. Don't paper over it. The user is testing whether you can self-correct on evidence, and they will trust you more after a clean correction than after a confident wrong answer that quietly gets buried.

5. **If logs are unavailable** (rotated, too old, or the question is about a future event), say **"I can't verify this from logs right now"** and offer to either: (a) dig into config / source instead, or (b) state the general principle clearly labeled as a **principle, not a verified fact about this session**.

## Pitfalls

- **Don't infer "主动发" / "cold start" / "I messaged first" from general knowledge about chat platforms.** A confident answer built on "bots usually need a handshake" is wrong if the log shows the first message was inbound. Read the log, count inbound vs outbound, then answer.
- **Don't confuse latency with agency.** A reply that arrives 5-10 s after the user's message feels proactive to the user. It is not. A message is "proactive" only if there is a `Sending response` line in the logs with **no preceding inbound** in the same session. If there is any inbound within the response window, the message is reactive.
- **Don't use the platform's general docs as the answer to "how did you specifically do this."** The docs describe what the platform allows; the logs describe what *this agent* did. The user is asking the second question.
- **Don't paste raw multi-MB log dumps.** Filter to the relevant session id, time window, and event type, then show a timeline. Full files are referenced, not inlined.
- **Don't generalize from one platform to another.** Feishu's `sender_id.open_id` field, Telegram's `from.id`, Discord's `author.id` are *equivalent* concepts but the field names and surrounding log lines differ — match the platform the user is on.
- **Don't answer "what does the platform allow" when the question is "what did you do."** "Feishu lets bots cold-message users with the right scope" is a different question from "did you cold-message me." Always answer the actual question.
- **Don't bury a wrong prior answer.** If you said X two turns ago and the evidence now shows Y, open with the correction. The user noticed; if you don't name it, they trust you less.
- **Don't claim a log line is the "first" without checking the full session window.** `tail -1` on a filtered stream can miss the actual first event because the gateway sometimes writes housekeeping lines (e.g. `mem_trim`) interleaved with platform events. Filter for the platform prefix (`[Feishu]`, `[Telegram]`, etc.) and pick the minimum timestamp.

## When NOT to use this skill

- The user is asking a **task question** ("can you do X", "how do I configure Y") — use the topic-specific skill, not this one.
- The user is asking a **factual** question ("what port does Feishu use") — answer from docs.
- The user is asking about a **future or hypothetical** ("if I added a new platform…") — answer with the general principle and label it as such.

## Output shape the user expects

When the user asks a meta-question, the response should usually contain:

1. **The answer** (one sentence)
2. **The evidence** (3-8 log lines or config excerpts with timestamps)
3. **The reasoning chain** (1-2 paragraphs)
4. **The correction note** if anything I said earlier was wrong (this is not optional — the user will ask "那你刚才说的呢" if I skip it)

Length: short when the evidence is one line, longer only when the chain is non-obvious. Never pad with disclaimers or restate the question.
