"""Explainable Decision Engine: an ordered log of architectural justifications.

Every rule engine writes a :class:`Rationale` entry for each decision it makes, so
the final report can answer *why* every medium, transceiver, subnet, routing
protocol and topology tier was chosen, with the numbers and standards behind it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Rationale:
    domain: str          # e.g. "L1 Media", "VLSM", "L3 Routing", "Topology"
    subject: str         # what the decision is about, e.g. a link or subnet name
    decision: str        # the chosen option
    justification: str   # natural-language explanation with numbers
    references: list[str] = field(default_factory=list)  # standards / RFCs

    def as_dict(self) -> dict:
        return {
            "domain": self.domain,
            "subject": self.subject,
            "decision": self.decision,
            "justification": self.justification,
            "references": self.references,
        }


class RationaleLog:
    def __init__(self) -> None:
        self.entries: list[Rationale] = []

    def add(self, domain: str, subject: str, decision: str, justification: str,
            references: list[str] | None = None) -> Rationale:
        entry = Rationale(domain, subject, decision, justification, references or [])
        self.entries.append(entry)
        return entry

    def by_domain(self, domain: str) -> list[Rationale]:
        return [e for e in self.entries if e.domain == domain]

    def __len__(self) -> int:
        return len(self.entries)

    def to_markdown(self) -> str:
        lines: list[str] = []
        domains: list[str] = []
        for e in self.entries:
            if e.domain not in domains:
                domains.append(e.domain)
        for d in domains:
            lines.append(f"### {d}\n")
            for e in self.by_domain(d):
                refs = f"  \n  _Refs: {', '.join(e.references)}_" if e.references else ""
                lines.append(f"- **{e.subject} → {e.decision}**  \n  {e.justification}{refs}")
            lines.append("")
        return "\n".join(lines)

    def to_text(self) -> str:
        out: list[str] = []
        for i, e in enumerate(self.entries, 1):
            out.append(f"[{i:02d}] [{e.domain}] {e.subject} -> {e.decision}")
            out.append(f"     WHY: {e.justification}")
            if e.references:
                out.append(f"     REF: {', '.join(e.references)}")
        return "\n".join(out)
