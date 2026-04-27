"""
Tests for the order state machine.

The state machine is the most critical component — if orders
can reach invalid states, the entire system is unreliable.
Every valid and invalid transition is tested explicitly.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.orders import Order, OrderState, OrderType, Side, InvalidTransition


class TestOrderCreation:
    def test_order_starts_in_created_state(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=2.0)
        assert order.state == OrderState.CREATED

    def test_order_has_unique_id(self):
        a = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        b = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        assert a.order_id != b.order_id

    def test_order_id_format(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        assert order.order_id.startswith("ORD-")

    def test_remaining_quantity_starts_full(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=5.0)
        assert order.remaining_quantity == 5.0

    def test_is_not_terminal_when_created(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        assert not order.is_terminal


class TestOrderStateTransitions:
    """Test every valid transition in the state machine."""

    def test_created_to_pending(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        assert order.state == OrderState.PENDING

    def test_created_to_rejected(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.REJECTED, reason="Risk check failed")
        assert order.state == OrderState.REJECTED
        assert order.rejection_reason == "Risk check failed"

    def test_pending_to_submitted(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        assert order.state == OrderState.SUBMITTED

    def test_pending_to_cancelled(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.CANCELLED)
        assert order.state == OrderState.CANCELLED

    def test_submitted_to_filled(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        order.transition_to(OrderState.FILLED)
        assert order.state == OrderState.FILLED

    def test_submitted_to_partial_fill(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        order.transition_to(OrderState.PARTIAL_FILL)
        assert order.state == OrderState.PARTIAL_FILL

    def test_partial_fill_to_filled(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        order.transition_to(OrderState.PARTIAL_FILL)
        order.transition_to(OrderState.FILLED)
        assert order.state == OrderState.FILLED


class TestInvalidTransitions:
    """Test that invalid transitions raise InvalidTransition."""

    def test_cannot_go_from_created_to_filled(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        with pytest.raises(InvalidTransition):
            order.transition_to(OrderState.FILLED)

    def test_cannot_go_from_filled_to_cancelled(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        order.transition_to(OrderState.FILLED)
        with pytest.raises(InvalidTransition):
            order.transition_to(OrderState.CANCELLED)

    def test_cannot_go_from_rejected_to_submitted(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.REJECTED)
        with pytest.raises(InvalidTransition):
            order.transition_to(OrderState.SUBMITTED)

    def test_cannot_go_from_cancelled_to_filled(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.CANCELLED)
        with pytest.raises(InvalidTransition):
            order.transition_to(OrderState.FILLED)

    def test_terminal_states_have_no_transitions(self):
        """FILLED, CANCELLED, REJECTED are terminal — no outgoing transitions."""
        for terminal in [OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED]:
            order = Order(symbol="ES", side=Side.BUY, quantity=1.0)
            # Get to terminal state
            if terminal == OrderState.FILLED:
                order.transition_to(OrderState.PENDING)
                order.transition_to(OrderState.SUBMITTED)
                order.transition_to(OrderState.FILLED)
            elif terminal == OrderState.CANCELLED:
                order.transition_to(OrderState.PENDING)
                order.transition_to(OrderState.CANCELLED)
            elif terminal == OrderState.REJECTED:
                order.transition_to(OrderState.REJECTED)

            assert order.is_terminal


class TestOrderFills:
    def test_full_fill_transitions_to_filled(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=2.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        order.apply_fill(4521.50, 2.0)
        assert order.state == OrderState.FILLED
        assert order.filled_quantity == 2.0
        assert order.remaining_quantity == 0.0

    def test_partial_fill(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=10.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        order.apply_fill(4521.50, 3.0)
        assert order.state == OrderState.PARTIAL_FILL
        assert order.filled_quantity == 3.0
        assert order.remaining_quantity == 7.0

    def test_multiple_partial_fills(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=10.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        order.apply_fill(100.0, 3.0)
        order.apply_fill(101.0, 3.0)
        order.apply_fill(102.0, 4.0)
        assert order.state == OrderState.FILLED
        assert order.fill_count == 3

    def test_vwap_average_fill_price(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=10.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        order.apply_fill(100.0, 5.0)  # 5 @ 100
        order.apply_fill(110.0, 5.0)  # 5 @ 110
        # VWAP = (500 + 550) / 10 = 105
        assert order.average_fill_price == 105.0

    def test_cannot_overfill(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=2.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        with pytest.raises(ValueError, match="exceeds remaining"):
            order.apply_fill(100.0, 5.0)

    def test_fill_ratio(self):
        order = Order(symbol="ES", side=Side.BUY, quantity=4.0)
        order.transition_to(OrderState.PENDING)
        order.transition_to(OrderState.SUBMITTED)
        order.apply_fill(100.0, 2.0)
        assert order.fill_ratio == 0.5
