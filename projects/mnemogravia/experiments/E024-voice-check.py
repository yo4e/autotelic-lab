"""E024: inspect a fictional mediated-voice packet, not the truth of testimony.

Python 3.10+, standard library only. No network or file writes.
All speakers, clauses, source links and grants are authored test fixtures.
This checks declared provenance and version scope, not semantic fidelity or consent.
"""
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json


@dataclass(frozen=True)
class Unit:
    id: str
    text: str


@dataclass(frozen=True)
class Clause:
    id: str
    text: str
    origin: str
    kind: str
    refs: tuple[str, ...]


@dataclass(frozen=True)
class Packet:
    source: tuple[Unit, ...]
    clauses: tuple[Clause, ...]
    residual: tuple[str, ...]
    purpose: str = "hearing_request"


@dataclass(frozen=True)
class Grant:
    digest: str
    scopes: frozenset[str]
    active: bool = True


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate(packet: Packet) -> None:
    source = {u.id: u.text for u in packet.source}
    if not source or len(source) != len(packet.source):
        raise ValueError("Source IDs must be nonempty and unique.")
    ids = [c.id for c in packet.clauses]
    if len(ids) != len(set(ids)):
        raise ValueError("Clause IDs must be unique.")
    if not set(packet.residual) <= source.keys():
        raise ValueError("Unknown residual reference.")
    covered = set(packet.residual)
    for c in packet.clauses:
        if c.origin not in {"speaker", "scribe"}:
            raise ValueError("Unknown declared origin.")
        if c.kind not in {"quote", "paraphrase", "interpretation"}:
            raise ValueError("Unknown clause kind.")
        if not c.refs or not set(c.refs) <= source.keys():
            raise ValueError("Unknown or missing source reference.")
        if c.kind == "interpretation" and c.origin != "scribe":
            raise ValueError("Interpretation cannot be relabeled as source speech.")
        if c.kind == "quote" and (len(c.refs) != 1 or c.text != source[c.refs[0]]):
            raise ValueError("Quoted bytes differ from source.")
        covered.update(c.refs)
    if covered != set(source):
        raise ValueError("A source unit vanished without a residual reference.")


def digest(packet: Packet) -> str:
    validate(packet)
    body = json.dumps(asdict(packet), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return sha256(body).hexdigest()


def inspect(packet: Packet, grant: Grant) -> dict:
    if not grant.scopes <= {"submit", "interpretation"}:
        raise ValueError("Unknown grant scope.")
    current = grant.active and grant.digest == digest(packet)
    return {
        "submission_permitted": current and "submit" in grant.scopes,
        "interpretation_endorsed": current and "interpretation" in grant.scopes,
        "origins": {c.id: c.origin for c in packet.clauses},
        "residual": list(packet.residual),
        "further_hearing_needed": bool(packet.residual),
        "truth": "not_evaluated",
    }


def fixture() -> Packet:
    units = (
        Unit("S1", "年代が正しいかは私にはわかりません。"),
        Unit("S2", "あのラベルが出てから、母の読み方はもう記録しなくていいと言われました。"),
        Unit("S3", "誰が決めたか、ラベルが理由なのかは知りません。"),
        Unit("S4", "展示を全部やめてほしいわけではありません。"),
        Unit("S5", "母の読み方も残して、どう扱うか私にも聞いてほしい。"),
        Unit("S6", "あそこに立つと、母の声の置き場所がなくなった感じがします。"),
    )
    clauses = (
        Clause("C1", "本人は成立年代を判定せず、因果と決定者も未確認。", "speaker", "paraphrase", ("S1", "S3")),
        Clause("C2", units[1].text, "speaker", "quote", ("S2",)),
        Clause("C3", "全面停止ではなく、記録の保存と本人への聴取を希望。", "speaker", "paraphrase", ("S4", "S5")),
        Clause("C4", "当事者範囲の再審として受理できる可能性がある。", "scribe", "interpretation", ("S2", "S5")),
    )
    return Packet(units, clauses, ("S6",))


def main() -> None:
    packet = fixture()
    key = digest(packet)
    changed = replace(packet, clauses=packet.clauses[:-1] + (
        replace(packet.clauses[-1], text="用途の再審として受理できる可能性がある。"),))
    source_changed = replace(packet, source=packet.source[:-1] + (
        replace(packet.source[-1], text="まだうまく言えません。"),))
    variants = {"baseline": packet, "draft_changed": changed,
                "source_changed": source_changed,
                "purpose_changed": replace(packet, purpose="permanent_record")}
    cases = {
        "unconfirmed": (packet, Grant(key, frozenset())),
        "submit_only": (packet, Grant(key, frozenset({"submit"}))),
        "interpretation_only": (packet, Grant(key, frozenset({"interpretation"}))),
        "both": (packet, Grant(key, frozenset({"submit", "interpretation"}))),
        "withdrawn": (packet, Grant(key, frozenset({"submit", "interpretation"}), False)),
        "stale_draft": (changed, Grant(key, frozenset({"submit", "interpretation"}))),
        "stale_source": (source_changed, Grant(key, frozenset({"submit", "interpretation"}))),
        "different_purpose": (variants["purpose_changed"], Grant(key, frozenset({"submit", "interpretation"}))),
    }
    named = {name: inspect(p, g) for name, (p, g) in cases.items()}
    expected = [(False, False), (True, False), (False, True), (True, True),
                (False, False), (False, False), (False, False), (False, False)]
    for out, pair in zip(named.values(), expected):
        require((out["submission_permitted"], out["interpretation_endorsed"]) == pair,
                "Named scope case failed.")
    checks = 0
    for p in variants.values():
        for submit, endorse, active, matching in product((False, True), repeat=4):
            scopes = frozenset(s for s, flag in (("submit", submit), ("interpretation", endorse)) if flag)
            grant = Grant(digest(p) if matching else "mismatch", scopes, active)
            before = digest(p)
            out = inspect(p, grant)
            require(out["submission_permitted"] == (submit and active and matching), "Submission scope.")
            require(out["interpretation_endorsed"] == (endorse and active and matching), "Endorsement scope.")
            require(out["origins"]["C4"] == "scribe", "Endorsement changed origin.")
            require(out["truth"] == "not_evaluated" and out["residual"] == ["S6"], "Truth or residual changed.")
            require(digest(p) == before, "Inspection mutated the packet.")
            checks += 1
    malformed = {
        "missing_residual": replace(packet, residual=()),
        "false_quote": replace(packet, clauses=(replace(packet.clauses[1], text="別の発言。"),) + packet.clauses[2:]),
        "unknown_reference": replace(packet, residual=("S999",)),
        "origin_laundering": replace(packet, clauses=packet.clauses[:-1] + (replace(packet.clauses[-1], origin="speaker"),)),
        "duplicate_source_id": replace(packet, source=packet.source + (packet.source[0],)),
    }
    rejected = []
    for name, invalid in malformed.items():
        try:
            digest(invalid)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("Malformed fixture passed: " + name)
    # A deceptive paraphrase with plausible metadata still passes: this is NOT NLP.
    hidden_drift = replace(packet, clauses=(replace(packet.clauses[0], text="本人は年代が誤りだと断定した。"),) + packet.clauses[1:])
    digest(hidden_drift)
    compact = {name: [out["submission_permitted"], out["interpretation_endorsed"]]
               for name, out in named.items()}
    print(json.dumps({
        "model": "E024-mediated-voice-v1",
        "kind": "authored_fixtures_not_empirical_observations",
        "named_case_columns": ["submission_permitted", "interpretation_endorsed"],
        "named_cases": compact,
        "packet_variants": len(variants), "grant_states_per_variant": 16,
        "finite_states_checked": checks, "malformed_packets_rejected": rejected,
        "counterexample": "A semantically false paraphrase with valid metadata passes.",
        "verified": ["scope_separation", "version_binding", "origin_not_rewritten_by_endorsement",
                     "residual_not_silence", "no_truth_inference", "no_mutation"],
        "not_verified": ["semantic_fidelity", "real_consent", "authenticity", "fairness"],
        "status": "PASS"
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
