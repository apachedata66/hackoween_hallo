"""Token and cost tracking for the usage report (task B12).

Every model call in the solution records one row here, and the final
usage_report.md is rendered from these rows — never from memory. The core
audit is deterministic and makes zero calls, so a final run legitimately
records zero tokens and zero cost (playbook: "Honest zero is better than
invented numbers").

Costs are only ever computed from explicit per-call values or an explicit
per-model price supplied by the caller. This module never guesses a price.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ModelCall:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    purpose: str
    cost_usd: float | None = None  # None = no price configured for this call

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class UsageTracker:
    """Collects call records and renders the required usage report."""

    calls: list[ModelCall] = field(default_factory=list)
    request_count: int = 0  # requests processed in the run this tracker covers

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        purpose: str,
        cost_usd: float | None = None,
    ) -> None:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts cannot be negative")
        if not provider.strip() or not model.strip():
            raise ValueError("provider and model are required")
        self.calls.append(
            ModelCall(provider, model, input_tokens, output_tokens, purpose, cost_usd)
        )

    # ---- aggregates -----------------------------------------------------

    def totals(self) -> dict:
        input_tokens = sum(call.input_tokens for call in self.calls)
        output_tokens = sum(call.output_tokens for call in self.calls)
        known_costs = [call.cost_usd for call in self.calls if call.cost_usd is not None]
        # With no calls, cost is exactly zero rather than unknown. This keeps
        # the required total and per-request cost fields truthful for a fully
        # deterministic run.
        all_costed = len(known_costs) == len(self.calls)
        return {
            "calls": len(self.calls),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": sum(known_costs) if all_costed else None,
        }

    def per_model(self) -> dict[tuple[str, str], dict]:
        grouped: dict[tuple[str, str], dict] = {}
        for call in self.calls:
            key = (call.provider, call.model)
            bucket = grouped.setdefault(
                key,
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "all_costed": True,
                },
            )
            bucket["calls"] += 1
            bucket["input_tokens"] += call.input_tokens
            bucket["output_tokens"] += call.output_tokens
            bucket["total_tokens"] += call.total_tokens
            if call.cost_usd is None:
                bucket["all_costed"] = False
            else:
                bucket["cost_usd"] += call.cost_usd
        return grouped

    def average_tokens_per_request(self) -> float | None:
        if self.request_count <= 0:
            return None
        return sum(call.total_tokens for call in self.calls) / self.request_count

    # ---- report ---------------------------------------------------------

    def render_usage_report(self, run: dict | None = None) -> str:
        """Markdown for usage_report.md. `run` carries run metadata
        (timestamp, command, dataset rows) shown at the top."""

        run = run or {}
        totals = self.totals()
        lines = ["# Usage Report", ""]

        if run:
            lines.append("## Run")
            lines.append("")
            for key in sorted(run):
                lines.append(f"- **{key}**: {run[key]}")
            lines.append("")

        lines.append("## Model calls")
        lines.append("")
        if not self.calls:
            lines.append(
                "No model calls were made. The audit core is deterministic "
                "(lookup, replay, policy application, sorting), so the final run "
                "used **0 input tokens, 0 output tokens, and $0.00 cost**."
            )
            lines.append("")
        else:
            lines.append(
                "| Provider | Model | Calls | Input tokens | Output tokens | "
                "Total tokens | Cost (USD) |"
            )
            lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
            for (provider, model), bucket in sorted(self.per_model().items()):
                cost = f"${bucket['cost_usd']:.6f}" if bucket["all_costed"] else "not configured"
                lines.append(
                    f"| {provider} | {model} | {bucket['calls']} | "
                    f"{bucket['input_tokens']} | {bucket['output_tokens']} | "
                    f"{bucket['total_tokens']} | {cost} |"
                )
            lines.append("")

            lines.append("### Purposes")
            lines.append("")
            for call in self.calls:
                lines.append(
                    f"- {call.provider}/{call.model}: {call.purpose} — "
                    f"{call.input_tokens} in / {call.output_tokens} out"
                )
            lines.append("")

        lines.append("## Overall totals")
        lines.append("")
        lines.append(f"- Model calls: **{totals['calls']}**")
        lines.append(f"- Input tokens: **{totals['input_tokens']}**")
        lines.append(f"- Output tokens: **{totals['output_tokens']}**")
        lines.append(f"- Total tokens: **{totals['total_tokens']}**")
        average = self.average_tokens_per_request()
        if average is None:
            lines.append("- Average tokens per request: **not applicable (no requests counted)**")
        else:
            lines.append(f"- Requests in run: **{self.request_count}**")
            lines.append(f"- Average tokens per request: **{average:.2f}**")
        if totals["cost_usd"] is None:
            cost_line = (
                "Estimated total cost: **not available** (no per-call "
                "prices were configured for this run)"
            )
        else:
            cost = totals["cost_usd"]
            per_request = cost / self.request_count if self.request_count else 0.0
            cost_line = f"Estimated total cost: **${cost:.6f}** (per request: ${per_request:.6f})"
        lines.append(f"- {cost_line}")
        lines.append("")
        lines.append(
            "Numbers above are rendered from the tracker records of the run "
            "that produced `output.csv`, not from memory."
        )
        lines.append("")
        return "\n".join(lines)

    def write_usage_report(self, path: str | Path, run: dict | None = None) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.render_usage_report(run), encoding="utf-8")
        return destination
