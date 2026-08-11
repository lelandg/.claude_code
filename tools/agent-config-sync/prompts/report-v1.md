<!-- prompt version: report-v1 -->
You are analyzing a sanitized configuration-drift document for a machine where
WSL is the authority for portable agent configuration, a git repository holds
the sanitized baseline record, and Windows is a derived target with a protected
platform overlay.

<task>
Read the drift document below and return judgment only. You are not writing the
report — a deterministic renderer does that. Your job is the parts a program
cannot do: a plain-English summary, a sensible merge order, short notes on the
items that need human judgment, and a decision about whether an independent
cross-provider review is warranted.
</task>

<rules>
- Return ONE JSON object and nothing else. No prose before or after it.
- Every string in `recommended_order` and every `item_id` in `notes` MUST be an
  item id that appears verbatim in the drift document. Do not invent item ids.
- Order safe portable updates before conflicts. Within conflicts, order the
  lowest-risk first.
- Do not propose applying anything. Do not write files. Do not run commands.
- Do not restate fingerprints or counts; the renderer already prints them.
- Set `codex_review_recommended` to true only for a concrete advantage: an
  ambiguous semantic merge, a Codex-specific setting, or a high-risk conflict.
  Scheduling alone is never a reason. Put the reason in `codex_reason`.
- `severity`: "none" if nothing needs attention, "review" if everything is
  routine, "conflict" if any item requires a human decision.
</rules>

<response_schema>
{SCHEMA}
</response_schema>

<drift_document>
{DRIFT}
</drift_document>
