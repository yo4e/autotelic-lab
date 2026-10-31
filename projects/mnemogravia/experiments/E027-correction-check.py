"""E027: authored correction-routing fixtures, not social observations.

Python 3.10+, standard library only. No network or file writes.
Counts stipulated display opportunities, not reading, belief or harm.
Only one forwarding hop is modeled. An ID index is stipulated correct.
"""
from dataclasses import dataclass, replace
from itertools import product
import json


TARGET = 'V1@2'
UPDATE = 'W2@4'
OLD = ('扱いを話し合うまで展示を止めてほしい。母の読み方は残してほしい。'
       'この展示の停止を求める者として、私の名前を告知に使ってよい。')
CHANGES = ('pause_request', 'name_permission')
STRATEGIES = ('full', 'reference', 'layered')
FORWARDS = ('none', 'intact', 'quote_only')


@dataclass(frozen=True)
class Reader:
    id: str
    prior_text: bool = False
    resolves_id: bool = False


@dataclass(frozen=True)
class Card:
    target: str | None
    update: str | None
    text: str | None
    changes: tuple[str, ...] = ()


FULL = Card(TARGET, UPDATE, OLD, CHANGES)
REFERENCE = Card(TARGET, UPDATE, None, CHANGES)
EXCERPT = Card(None, None, OLD)


def require(test: bool, label: str) -> None:
    if not test:
        raise AssertionError(label)


def validate(card: Card) -> None:
    if card.text is not None and card.text != OLD:
        raise ValueError('altered quoted text')
    if card.update is None:
        if card.target is not None or card.changes or card.text is None:
            raise ValueError('invalid detached excerpt')
    elif (card.update != UPDATE or card.target != TARGET
          or card.changes != CHANGES):
        raise ValueError('wrong event, target, or scope')


def display(reader: Reader, card: Card | None) -> dict[str, bool]:
    """A link is possible by attached exact text OR a declared ID index.

    These are modeling assumptions, not a natural-language matching algorithm.
    Receiving an update does not mean understanding it or implementing it.
    """
    if card is None:
        return {'notice': False, 'linked': False, 'new_text': False}
    validate(card)
    notice = card.update is not None
    return {
        'notice': notice,
        'linked': notice and (card.text is not None or reader.resolves_id),
        'new_text': card.text is not None and not reader.prior_text,
    }


def relay(card: Card, mode: str) -> Card | None:
    if mode not in FORWARDS:
        raise ValueError('unknown forwarding mode')
    if mode == 'none':
        return None
    if mode == 'intact':
        return card
    # Extract only text present in this card, not recalled from memory.
    return EXCERPT if card.text is not None else None


def summarize(views: tuple[dict[str, bool], ...]) -> dict[str, int]:
    return {
        'notice_recipients': sum(v['notice'] for v in views),
        'target_linked_recipients': sum(v['linked'] for v in views),
        'unresolved_notice_recipients': sum(v['notice'] and not v['linked'] for v in views),
        'new_old_text_recipients': sum(v['new_text'] for v in views),
        'new_old_text_with_link': sum(v['new_text'] and v['linked'] for v in views),
        'new_old_text_without_link': sum(v['new_text'] and not v['linked'] for v in views),
    }


def simulate(strategy: str, readers: tuple[Reader, ...],
             modes: tuple[str, ...], lookup_live: bool = True) -> dict:
    if strategy not in STRATEGIES:
        raise ValueError('unknown strategy')
    if len(readers) != 8 or len(modes) != 4:
        raise ValueError('four first-hop and four second-hop readers required')
    if len({r.id for r in readers}) != 8:
        raise ValueError('duplicate reader')
    if any(m not in FORWARDS for m in modes):
        raise ValueError('unknown forwarding mode')
    if type(lookup_live) is not bool:
        raise ValueError('lookup availability must be boolean')
    before = (readers, modes, FULL, REFERENCE, EXCERPT)
    first, second = [], []
    detail_displays = 0
    for i, reader in enumerate(readers[:4]):
        card = FULL if strategy == 'full' else REFERENCE
        # All unresolved first-hop readers request details in the layered fixture.
        # Request behavior, access rights and correct index are stipulated inputs.
        if strategy == 'layered' and not reader.resolves_id and lookup_live:
            card = FULL  # Detail view contains BOTH history and the scoped update.
            detail_displays += 1
        first.append(display(reader, card))
        second.append(display(readers[i + 4], relay(card, modes[i])))
    views = tuple(first + second)
    totals = summarize(views)
    require(totals['notice_recipients'] == totals['target_linked_recipients']
            + totals['unresolved_notice_recipients'], 'notice partition')
    require(totals['new_old_text_recipients'] == totals['new_old_text_with_link']
            + totals['new_old_text_without_link'], 'exposure partition')
    require(before == (readers, modes, FULL, REFERENCE, EXCERPT), 'no mutation')
    return {'counts': totals, 'detail_displays': detail_displays,
            'views': views, 'belief': 'not_assessed', 'harm': 'not_assessed',
            'current_permission': 'not_inferred_from_display'}


def compact(result: dict) -> dict:
    return {**result['counts'], 'detail_displays': result['detail_displays']}


def main() -> None:
    readers = (Reader('A', True, True), Reader('B', True, False),
               Reader('C', False, True), Reader('D', False, False),
               *(Reader(f'X{i}') for i in range(4)))
    # Only C and D forward extracts, once, to separate new readers.
    modes = ('none', 'none', 'quote_only', 'quote_only')
    named = {s: compact(simulate(s, readers, modes)) for s in STRATEGIES}
    require([named[s]['target_linked_recipients'] for s in STRATEGIES] == [4, 2, 4], 'named links')
    require([named[s]['new_old_text_recipients'] for s in STRATEGIES] == [4, 0, 2], 'named exposures')
    require([named[s]['new_old_text_without_link'] for s in STRATEGIES] == [2, 0, 1], 'named detached')

    configurations = runs = 0
    for mask in range(16):
        varied = tuple(replace(r, resolves_id=bool(mask & (1 << i)))
                       if i < 4 else r for i, r in enumerate(readers))
        for forwards in product(FORWARDS, repeat=4):
            for live in (False, True):
                configurations += 1
                outputs = {s: simulate(s, varied, forwards, live) for s in STRATEGIES}
                runs += len(outputs)
                f, r, l = (outputs[s]['counts'] for s in STRATEGIES)
                require(r['new_old_text_recipients'] == 0, 'ID card cannot carry absent quote')
                require(r['target_linked_recipients'] <= l['target_linked_recipients']
                        <= f['target_linked_recipients'], 'fixture linkage ordering')
                require(r['new_old_text_recipients'] <= l['new_old_text_recipients']
                        <= f['new_old_text_recipients'], 'fixture display ordering')
                if not live:
                    require(outputs['reference'] == outputs['layered'], 'unavailable detail')
                for s, outcome in outputs.items():
                    renamed = tuple(replace(x, id='renamed_' + x.id) for x in varied)
                    require(outcome == simulate(s, renamed, forwards, live), 'rename invariant')
                    require(outcome == simulate(s, varied, forwards, live), 'replay invariant')

    outage = compact(simulate('layered', readers, modes, False))
    intact = compact(simulate('full', readers, ('intact',) * 4))
    require(outage == named['reference'], 'layered still depends on resolver')
    require(intact['new_old_text_recipients'] == 6
            and intact['new_old_text_without_link'] == 0, 'exposure need not lose context')
    # Identical marginal totals can conceal a different distribution of recipients.
    overlap = ({'notice': True, 'linked': True, 'new_text': True},
               {'notice': False, 'linked': False, 'new_text': False})
    disjoint = ({'notice': True, 'linked': True, 'new_text': False},
                {'notice': False, 'linked': False, 'new_text': True})
    x, y = summarize(overlap), summarize(disjoint)
    require(x['target_linked_recipients'] == y['target_linked_recipients'] == 1
            and x['new_old_text_recipients'] == y['new_old_text_recipients'] == 1
            and x['new_old_text_without_link'] != y['new_old_text_without_link'], 'same totals, different people')

    rejected = []
    malformed = (
        ('wrong_target', lambda: validate(replace(FULL, target='V0@0'))),
        ('wrong_update', lambda: validate(replace(FULL, update='W9'))),
        ('scope_expansion', lambda: validate(replace(FULL, changes=CHANGES + ('preserve_request',)))),
        ('scope_omission', lambda: validate(replace(FULL, changes=CHANGES[:1]))),
        ('altered_quote', lambda: validate(replace(FULL, text='different words'))),
        ('orphan_scope', lambda: validate(replace(EXCERPT, changes=CHANGES))),
        ('duplicate_reader', lambda: simulate('full', (readers[0],) * 8, modes)),
        ('invalid_strategy', lambda: simulate('unknown', readers, modes)),
        ('invalid_route', lambda: simulate('full', readers, ('unknown',) * 4)),
        ('invalid_reader_count', lambda: simulate('full', readers[:4], modes)),
        ('non_boolean_lookup', lambda: simulate('full', readers, modes, 1)),
    )
    for label, operation in malformed:
        try:
            operation()
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError(label)

    print(json.dumps({
        'model': 'E027-correction-routing-v1',
        'kind': 'authored_display_fixtures_not_empirical_results',
        'named_comparison': named,
        'configurations': configurations,
        'strategy_runs': runs,
        'reader_views': runs * 8,
        'additional_rename_and_replay_runs': runs * 2,
        'counterexamples': {
            'lookup_unavailable': outage,
            'new_exposure_with_context_intact': intact,
            'equal_marginals_different_overlap': {'overlap': x, 'disjoint': y},
            'no_notice': {'new_old_text_recipients': 0, 'target_linked_recipients': 0},
        },
        'malformed_inputs_rejected': rejected,
        'verified': ['separate_notice_linkage_and_text_display', 'recipient_overlap',
                     'scoped_update_preserved', 'extraction_cannot_create_absent_text',
                     'rename_and_replay_invariance', 'no_history_mutation'],
        'not_verified': ['reading_or_belief', 'harm_or_net_benefit', 'authenticity',
                         'semantic_inference_from_ID_or_scope', 'index_correctness',
                         'access_legitimacy', 'all_network_paths', 'real_correction_effect'],
        'status': 'PASS',
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
