"""E028: authored correction-target fixtures, not a historical authenticator.

Python 3.10+, standard library only. No network or file writes.
A confirmed binding is a supplied assumption, not a computed verification.
"""
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product, permutations
import json

FIELDS = frozenset({'pause_request', 'name_permission', 'preserve_request'})


@dataclass(frozen=True)
class Ref:
    space: str
    epoch: int
    local: str
    revision: int


@dataclass(frozen=True)
class Record:
    occurrence: str
    ref: Ref
    speaker: str
    issued: int
    text: str
    values: tuple[tuple[str, bool], ...]


@dataclass(frozen=True)
class Notice:
    identifier: str
    target: Ref
    speaker: str
    issued: int
    scope: tuple[str, ...]


@dataclass(frozen=True)
class Binding:
    old_ref: Ref
    instance: Ref
    occurrence: str
    speaker: str
    issued: int
    digest: str
    basis: str
    confirmed: bool


def digest(text: str) -> str:
    return sha256(text.encode('utf-8')).hexdigest()


def require(ok: bool, label: str) -> None:
    if not ok:
        raise AssertionError(label)


def validate(n: Notice, records: tuple, bindings: tuple) -> None:
    if not n.scope or len(set(n.scope)) != len(n.scope) or not set(n.scope) <= FIELDS:
        raise ValueError('invalid notice scope')
    if len({r.occurrence for r in records}) != len(records):
        raise ValueError('duplicate occurrence')
    for ref in (n.target,) + tuple(r.ref for r in records) + tuple(b.old_ref for b in bindings) + tuple(b.instance for b in bindings):
        if not ref.space or not ref.local or type(ref.epoch) is not int or type(ref.revision) is not int or min(ref.epoch, ref.revision) < 1:
            raise ValueError('invalid qualified reference')
    for r in records:
        if not r.occurrence or not r.speaker or type(r.issued) is not int or r.issued < 0:
            raise ValueError('invalid record metadata')
        if len(r.values) != len(FIELDS) or {k for k, _ in r.values} != FIELDS or any(type(v) is not bool for _, v in r.values):
            raise ValueError('invalid recorded values')
    if not n.identifier or not n.speaker or type(n.issued) is not int or n.issued < 0:
        raise ValueError('invalid notice metadata')
    for b in bindings:
        if b.basis not in ('surviving_register', 'reconstruction') or type(b.confirmed) is not bool:
            raise ValueError('invalid binding basis or confirmation')
        if len(b.digest) != 64 or any(c not in '0123456789abcdef' for c in b.digest):
            raise ValueError('invalid fingerprint syntax')
        if not b.occurrence or not b.speaker or type(b.issued) is not int or b.issued < 0:
            raise ValueError('invalid binding metadata')


def assess(n: Notice, records: tuple, bindings: tuple) -> dict:
    validate(n, records, bindings)
    rows = tuple(b for b in bindings if b.old_ref == n.target)
    identities = {(b.occurrence, b.instance, b.speaker, b.issued, b.digest) for b in rows}
    target = None
    if not identities:
        state = 'unresolved'
    elif len(identities) > 1:
        state = 'conflicting_bindings'
    elif not any(b.confirmed for b in rows):
        state = 'proposal_only'
    else:
        occurrence, instance, speaker, issued, fingerprint = next(iter(identities))
        r = next((r for r in records if r.occurrence == occurrence), None)
        if r is None:
            state = 'target_unavailable'
        elif r.ref != instance or speaker != r.speaker or speaker != n.speaker:
            state = 'identity_mismatch'
        elif r.issued != issued or r.issued > n.issued:
            state = 'time_mismatch'
        elif digest(r.text) != fingerprint:
            state = 'content_mismatch'
        else:
            state, target = 'ready_under_assumptions', occurrence
    projections = {}
    for r in sorted(records, key=lambda r: r.occurrence):
        values = dict(r.values)
        if r.occurrence == target:
            values.update({k: False for k in n.scope})
        projections[r.occurrence] = values
    return {
        'resolution': state,
        'candidate_ids': sorted({b.occurrence for b in rows}),
        'applied_target': target,
        'projection': projections,
        'orphan_notice_retained': target is None,
        'present_authorization': 'not_inferred',
        'historical_truth': 'not_assessed',
        'binding_authenticity': 'assumed_not_certified',
    }


def fixtures():
    ref = Ref('archive-A', 1, 'V1', 2)
    text = '展示を止めてほしい。母の読み方は残してほしい。私の名前を告知に使ってよい。'
    values = tuple((k, True) for k in sorted(FIELDS))
    a = Record('A', ref, 'P', 2, text, values)
    records = (a, replace(a, occurrence='B', speaker='Q', ref=replace(ref, space='archive-B')),
               replace(a, occurrence='C', ref=replace(ref, epoch=2), issued=3),
               replace(a, occurrence='D', ref=replace(ref, revision=3), issued=3))
    n = Notice('W2@4', Ref('notice-registry', 1, 'V1', 2), 'P', 4, ('pause_request', 'name_permission'))
    b = Binding(n.target, ref, 'A', 'P', 2, digest(text), 'surviving_register', True)
    return n, records, b


def main() -> None:
    n, records, b = fixtures()
    named_inputs = {
        'confirmed_original': (records, (b,)),
        'missing_table': (records, ()),
        'one_reconstructed_candidate': (records, (replace(b, basis='reconstruction', confirmed=False),)),
        'other_speaker_same_text': (records, (replace(b, occurrence='B'),)),
        'reused_local_number': (records, (replace(b, occurrence='C'),)),
        'different_revision': (records, (replace(b, occurrence='D'),)),
        'two_targets': (records, (b, replace(b, occurrence='C'))),
        'target_not_accessible': (records[1:], (b,)),
        'confirmed_reconstruction': (records, (replace(b, basis='reconstruction'),)),
        'wrong_content': (records, (replace(b, digest='0' * 64),)),
        'wrong_time': (records, (replace(b, issued=3),)),
        'other_namespace_only': (records, (replace(b, old_ref=replace(n.target, space='elsewhere')),)),
    }
    expected = ('ready_under_assumptions', 'unresolved', 'proposal_only',
                'identity_mismatch', 'identity_mismatch', 'identity_mismatch',
                'conflicting_bindings', 'target_unavailable', 'ready_under_assumptions',
                'content_mismatch', 'time_mismatch', 'unresolved')
    named = {}
    for (label, (rs, bs)), wanted in zip(named_inputs.items(), expected):
        out = assess(n, rs, bs)
        require(out['resolution'] == wanted, label)
        named[label] = out['resolution']

    states = ready = 0
    scopes = (('pause_request',), ('name_permission',), n.scope)
    for occurrence, basis, confirmed, good_digest, good_time, scope in product(
            'ABCD', ('surviving_register', 'reconstruction'), (False, True),
            (False, True), (False, True), scopes):
        nn = replace(n, scope=scope)
        bb = replace(b, occurrence=occurrence, basis=basis, confirmed=confirmed,
                     digest=b.digest if good_digest else '0' * 64,
                     issued=2 if good_time else 3)
        before = (nn, records, bb)
        out = assess(nn, records, (bb,))
        applied = occurrence == 'A' and confirmed and good_digest and good_time
        require((out['applied_target'] == 'A') == applied, 'identity before application')
        for r in records:
            expected_values = dict(r.values)
            if applied and r.occurrence == 'A':
                expected_values.update({k: False for k in scope})
            require(out['projection'][r.occurrence] == expected_values, 'no spillover')
        require(out == assess(nn, tuple(reversed(records)), (bb, bb)), 'order and retry')
        require(before == (nn, records, bb), 'no mutation')
        require(out['present_authorization'] == 'not_inferred', 'no default permission')
        states += 1
        ready += applied

    conflict = (b, replace(b, occurrence='C', basis='reconstruction', confirmed=False))
    orders = 0
    for rs in permutations(records):
        for bs in permutations(conflict):
            require(assess(n, rs, bs)['resolution'] == 'conflicting_bindings', 'no first-row winner')
            orders += 1
    empty = assess(n, records, ())
    require(empty['applied_target'] is None, 'two indistinguishable lost-table worlds')
    proposed = replace(b, occurrence='C', instance=records[2].ref, issued=3, basis='reconstruction', confirmed=False)
    single = assess(n, (records[2],), (proposed,))
    require(single['resolution'] == 'proposal_only', 'survival is not evidence')
    require(len({digest(r.text) for r in records}) == 1, 'same text different occurrences')
    forged = replace(records[0], occurrence='X')
    false_input = assess(n, (forged,), (replace(b, occurrence='X'),))
    require(false_input['applied_target'] == 'X', 'coherent false metadata is not detected')
    late = replace(records[0], issued=5)
    require(assess(n, (late,), (replace(b, issued=5),))['resolution'] == 'time_mismatch', 'future target')
    renamed = tuple(replace(r, speaker='P-renamed' if r.speaker == 'P' else r.speaker) for r in records)
    require(assess(replace(n, speaker='P-renamed'), renamed, (replace(b, speaker='P-renamed'),)) == assess(n, records, (b,)), 'consistent renaming')

    bad = {
        'empty_scope': (replace(n, scope=()), records, (b,)),
        'unknown_scope': (replace(n, scope=('truth',)), records, (b,)),
        'duplicate_scope': (replace(n, scope=('pause_request',) * 2), records, (b,)),
        'duplicate_occurrence': (n, records + (records[0],), (b,)),
        'invalid_revision': (replace(n, target=replace(n.target, revision=0)), records, (b,)),
        'invalid_fingerprint': (n, records, (replace(b, digest='xyz'),)),
        'invalid_basis': (n, records, (replace(b, basis='looks_similar'),)),
        'non_boolean_confirmation': (n, records, (replace(b, confirmed='yes'),)),
        'invalid_values': (n, (replace(records[0], values=(('pause_request', True),)),), (b,)),
    }
    rejected = []
    for label, args in bad.items():
        try:
            assess(*args)
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError('accepted invalid input: ' + label)
    print(json.dumps({
        'model': 'E028-orphaned-correction-v1',
        'kind': 'authored_binding_fixtures_not_empirical_results',
        'named_cases': named, 'finite_states_checked': states,
        'ready_under_assumptions_states': ready, 'conflict_order_checks': orders,
        'counterexamples': {
            'same_text_different_occurrences': {'records': 4, 'distinct_text_fingerprints': 1},
            'single_surviving_candidate': single['resolution'],
            'lost_table_two_worlds': {'visible_input_identical': True, 'intended_targets': ['A', 'C'], 'output': empty['resolution']},
            'coherent_false_binding_passes': false_input['resolution'],
        },
        'malformed_inputs_rejected': rejected,
        'verified': ['proposal_is_not_application', 'qualified_occurrence_and_version',
                     'scope_is_not_expanded', 'conflicts_are_not_majority_votes',
                     'retry_order_and_renaming_invariance', 'history_preserved',
                     'unresolved_is_not_current_permission'],
        'not_verified': ['binding_authenticity', 'free_consent', 'semantic_matching',
                         'access_rights', 'complete_catalog', 'operational_safety', 'legal_effect'],
        'status': 'PASS',
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
