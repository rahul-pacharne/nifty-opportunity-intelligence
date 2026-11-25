from decimal import Decimal

from app.core.constants import IndexSymbol
from app.runtime.research_gate import evaluate_index


def _pattern() -> list[Decimal]:
    balanced = ([Decimal("1"), Decimal("-1")] * 11) + [Decimal("1")]
    return balanced + [Decimal("1")] * 6


def test_a_losing_option_book_is_visible_and_not_approved() -> None:
    report = evaluate_index(_pattern(), index=IndexSymbol.NIFTY, option_net=Decimal("-25"))
    assert report.approved is False
    assert report.option_net == Decimal("-25")
    assert report.sample_size == 6
    assert report.model_brier != report.baseline_brier


def test_one_index_can_be_approved_while_the_other_stays_silent() -> None:
    nifty = evaluate_index(_pattern(), index=IndexSymbol.NIFTY, option_net=Decimal("10"))
    bank = evaluate_index(_pattern(), index=IndexSymbol.BANKNIFTY, option_net=Decimal("-1"))
    assert nifty.approved is True
    assert bank.approved is False
    assert nifty.model_brier < nifty.baseline_brier
