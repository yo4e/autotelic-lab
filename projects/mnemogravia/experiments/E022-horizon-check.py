"""E022: check a fictional scoped-use permit, not historical truth or legitimacy.

Run with Python 3.10+; standard library only. No network access or file mutation.
All inputs are stipulated model states, not measurements of people or archives.
"""
from dataclasses import dataclass, replace
from itertools import product
import json


@dataclass(frozen=True)
class Dossier:
    revision: str = "B1"
    epistemic_status: str = "provisionally_supported"


@dataclass(frozen=True)
class Permit:
    dossier_revision: str = "B1"
    purpose: str = "annotated_exhibit"
    affected: frozenset[str] = frozenset({"cataloguers", "visitors"})
    valid_from: int = 31
    valid_until: int = 32  # Exclusive: generation 32 requires a new decision.


@dataclass(frozen=True)
class Context:
    manager: str = "K1"
    purpose: str = "annotated_exhibit"
    affected: frozenset[str] = frozenset({"cataloguers", "visitors"})
    reversible: bool = True
    generation: int = 31
    mandate_active: bool = True
    objection_pending: bool = False


def assess(permit: Permit, dossier: Dossier, context: Context) -> dict:
    """Check scope under stipulated facts; do not infer truth from authorization."""
    if permit.valid_until <= permit.valid_from:
        raise ValueError("Permit interval must be non-empty.")
    conditions = (
        (dossier.revision != permit.dossier_revision, "evidence_changed"),
        (context.purpose != permit.purpose, "purpose_changed"),
        (context.affected != permit.affected, "affected_changed"),
        (not context.reversible, "irreversible_use"),
        (context.generation < permit.valid_from, "not_yet_valid"),
        (context.generation >= permit.valid_until, "expired"),
        (not context.mandate_active, "mandate_withdrawn"),
        (context.objection_pending, "objection_pending"),
    )
    reasons = [name for triggered, name in conditions if triggered]
    return {
        "authorization": "review_required" if reasons else "in_scope",
        "reasons": reasons,
        "epistemic_status": dossier.epistemic_status,
    }


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    permit, dossier, context = Permit(), Dossier(), Context()
    scenarios = (
        ("baseline", dossier, context, []),
        ("manager_changed", dossier, replace(context, manager="K2"), []),
        ("purpose_changed", dossier, replace(context, purpose="permanent_exclusion"), ["purpose_changed"]),
        ("affected_changed", dossier, replace(context, affected=context.affected | {"dissenting_archive"}), ["affected_changed"]),
        ("irreversible_use", dossier, replace(context, reversible=False), ["irreversible_use"]),
        ("before_start", dossier, replace(context, generation=30), ["not_yet_valid"]),
        ("at_expiry", dossier, replace(context, generation=32), ["expired"]),
        ("new_evidence", Dossier("B2", "contested"), context, ["evidence_changed"]),
        ("mandate_withdrawn", dossier, replace(context, mandate_active=False), ["mandate_withdrawn"]),
        ("objection", dossier, replace(context, objection_pending=True), ["objection_pending"]),
    )
    named = {}
    for name, evidence, situation, expected in scenarios:
        outcome = assess(permit, evidence, situation)
        require(outcome["reasons"] == expected, name)
        require(outcome["epistemic_status"] == evidence.epistemic_status, name)
        named[name] = outcome["authorization"]

    states = decisions = approvals = 0
    for flags in product((False, True), repeat=6):
        changed_evidence, changed_use, changed_people, irreversible, revoked, objection = flags
        evidence = Dossier("B2", "contested") if changed_evidence else dossier
        for generation in (30, 31, 32):
            states += 1
            situation = replace(
                context,
                purpose="permanent_exclusion" if changed_use else context.purpose,
                affected=context.affected | {"dissenting_archive"} if changed_people else context.affected,
                reversible=not irreversible,
                generation=generation,
                mandate_active=not revoked,
                objection_pending=objection,
            )
            outputs = [assess(permit, evidence, replace(situation, manager=name))
                       for name in ("K1", "K2", "K3")]
            require(outputs[0] == outputs[1] == outputs[2], "identity invariant")
            expected_active = not any(flags) and generation == 31
            for outcome in outputs:
                decisions += 1
                active = outcome["authorization"] == "in_scope"
                require(active == expected_active, "scope invariant")
                require(outcome["epistemic_status"] == evidence.epistemic_status, "no truth promotion")
                approvals += int(active)

    try:
        assess(replace(permit, valid_until=31), dossier, context)
    except ValueError:
        invalid_interval_rejected = True
    else:
        raise AssertionError("invalid interval was not rejected")

    print(json.dumps({
        "model": "E022-scoped-horizon-v1",
        "kind": "stipulated_fictional_model_checks_not_empirical_results",
        "named_scenarios": named,
        "contexts_exhausted": states,
        "manager_variants": 3,
        "decisions_checked": decisions,
        "in_scope_decisions": approvals,
        "review_required_decisions": decisions - approvals,
        "invalid_interval_rejected": invalid_interval_rejected,
        "invariants": ["identity_independent_under_same_mandate", "scope_changes_trigger_review", "authorization_never_promotes_truth"],
        "status": "PASS",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
