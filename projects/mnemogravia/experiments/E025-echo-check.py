"""E025: inspect declared information lineage for one claim, not truth.

Python 3.10+, standard library only. All fixtures are authored fiction.
Each Unit is a claim component, not a whole person or whole testimony.
Parents mean claim-relevant information was used or encountered. They do
not quantify influence. Absence of an edge never certifies independence.
The program prints JSON only; it does not write files or access a network.
"""
from dataclasses import dataclass, replace
from itertools import product
import json


@dataclass(frozen=True)
class Unit:
    id: str
    time: int
    parents: tuple[str, ...] = ()
    speaker: str = "unspecified"


class Lineage:
    def __init__(self, units: tuple[Unit, ...]):
        self.units = {u.id: u for u in units}
        if len(self.units) != len(units):
            raise ValueError("duplicate_id")
        for u in units:
            if not u.id or len(set(u.parents)) != len(u.parents):
                raise ValueError("invalid_unit")
            for parent in u.parents:
                if parent not in self.units:
                    raise ValueError("unknown_parent")
                if self.units[parent].time >= u.time:
                    raise ValueError("non_forward_link")

    def ancestors(self, key: str) -> frozenset[str]:
        if key not in self.units:
            raise ValueError("unknown_unit")
        found, pending = set(), [key]
        while pending:
            item = pending.pop()
            if item not in found:
                found.add(item)
                pending.extend(self.units[item].parents)
        return frozenset(found)

    def relation(self, candidate: str, draft: str) -> str:
        c, d = self.ancestors(candidate), self.ancestors(draft)
        if candidate == draft:
            return "same_record"
        if draft in c:
            return "downstream_of_draft"
        if candidate in d:
            return "already_used_by_draft"
        if c & d:
            return "shared_ancestor"
        return "no_recorded_link"


ADOPTIONS = ("adopted", "rejected", "undecided", "unrecorded")


def inspect(graph: Lineage, candidates: tuple[str, ...], adoption: str) -> dict:
    """Keep declared present position separate from lineage and truth."""
    if adoption not in ADOPTIONS:
        raise ValueError("invalid_adoption")
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError("invalid_candidates")
    relations = {key: graph.relation(key, "M") for key in candidates}
    return {
        "present_position_as_declared": adoption,
        "relations": relations,
        "linked_components": sorted(k for k, v in relations.items()
                                    if v != "no_recorded_link"),
        "separate_inquiry_candidates": sorted(k for k, v in relations.items()
                                              if v == "no_recorded_link"),
        "independence": "not_certified",
        "truth": "not_assessed",
    }


def require(condition: bool, label: str) -> None:
    # Do not use assert: checks must remain active under python -O.
    if not condition:
        raise AssertionError(label)


def fixture() -> tuple[Unit, ...]:
    return (
        Unit("S", 0, speaker="claimant"),
        Unit("D", 0, speaker="separate_archive"),
        Unit("M", 1, ("S",), "scribe"),
        Unit("L", 2, ("M",), "intermediary"),
        Unit("R", 3, ("L",), "claimant"),
        Unit("C", 3, ("S",), "other_reporter"),
        Unit("E", 3, ("D",), "claimant"),
    )


def main() -> None:
    units = fixture()
    graph = Lineage(units)
    named = {
        "direct_echo": graph.relation("L", "M"),
        "indirect_echo": graph.relation("R", "M"),
        "shared_original": graph.relation("C", "M"),
        "separate_archive": graph.relation("E", "M"),
        "same_record": graph.relation("M", "M"),
        "original_already_used": graph.relation("S", "M"),
    }
    expected = {
        "direct_echo": "downstream_of_draft",
        "indirect_echo": "downstream_of_draft",
        "shared_original": "shared_ancestor",
        "separate_archive": "no_recorded_link",
        "same_record": "same_record",
        "original_already_used": "already_used_by_draft",
    }
    require(named == expected, "named relations")
    mixed = inspect(graph, ("R", "E"), "adopted")
    require(mixed["linked_components"] == ["R"], "component partition")
    require(mixed["separate_inquiry_candidates"] == ["E"], "new component kept")

    count = 0
    for draft_uses_s, first, second, third, reuses_s in product((False, True), repeat=5):
        sample = (
            Unit("S", 0),
            Unit("M", 1, ("S",) if draft_uses_s else ()),
            Unit("X", 2, ("M",) if first else ()),
            Unit("Y", 3, ("X",) if second else ()),
            Unit("R", 4, (("Y",) if third else ()) + (("S",) if reuses_s else ())),
        )
        g = Lineage(sample)
        expected_relation = (
            "downstream_of_draft" if first and second and third else
            "shared_ancestor" if draft_uses_s and reuses_s else
            "no_recorded_link"
        )
        for adoption in ADOPTIONS:
            output = inspect(g, ("R",), adoption)
            require(output["relations"]["R"] == expected_relation, "path rule")
            require(output["present_position_as_declared"] == adoption, "position kept")
            require(output["truth"] == "not_assessed", "no truth promotion")
            require(output["independence"] == "not_certified", "no independence promotion")
            renamed = Lineage(tuple(replace(u, speaker="different_name") for u in sample))
            require(inspect(renamed, ("R",), adoption) == output, "name is not lineage")
            require(tuple(g.units.values()) == sample, "history unchanged")
            count += 1

    malformed = {
        "duplicate_id": (Unit("S", 0), Unit("S", 1)),
        "unknown_parent": (Unit("S", 0, ("missing",)),),
        "self_reference": (Unit("S", 0, ("S",)),),
        "backwards_link": (Unit("S", 0, ("M",)), Unit("M", 1)),
        "duplicate_parent": (Unit("S", 0), Unit("M", 1, ("S", "S"))),
    }
    rejected = []
    for name, bad in malformed.items():
        try:
            Lineage(bad)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name)
    for name, candidates, adoption in (
        ("unknown_candidate", ("missing",), "adopted"),
        ("duplicate_candidate", ("R", "R"), "adopted"),
        ("invalid_adoption", ("R",), "yes_maybe"),
    ):
        try:
            inspect(graph, candidates, adoption)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name)

    # A real blind spot: silently omitting an influence link is well-formed.
    omitted = Lineage(tuple(replace(u, parents=()) if u.id == "L" else u for u in units))
    before, after = graph.relation("R", "M"), omitted.relation("R", "M")
    require(before == "downstream_of_draft" and after == "no_recorded_link", "blind spot")
    require(inspect(omitted, ("R",), "adopted")["independence"] == "not_certified",
            "unknown is not independent")

    print(json.dumps({
        "model": "E025-second-original-v1",
        "kind": "authored_claim_lineage_fixtures_not_empirical_results",
        "named_relations": named,
        "mixed_packet": mixed,
        "graph_variants": 32,
        "adoption_states": 4,
        "finite_states_checked": count,
        "malformed_inputs_rejected": rejected,
        "missing_link_counterexample": {"before": before, "after": after,
                                        "independence": "not_certified"},
        "verified": ["direct_and_indirect_paths", "claim_component_partition",
                     "adoption_does_not_rewrite_lineage", "speaker_rename_invariant",
                     "no_truth_or_independence_promotion", "no_history_mutation"],
        "not_verified": ["actual_authorship", "free_consent", "historical_truth",
                         "semantic_fidelity", "complete_dependencies", "statistical_independence"],
        "status": "PASS"
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
