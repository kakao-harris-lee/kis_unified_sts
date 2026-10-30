"""Wire one-use stock holding proofs to the existing asynchronous witness worker."""

from __future__ import annotations

from collections.abc import Callable

from tos.engine.records import StageRequest
from tos.rcl import CapacityState

from tos_runtime.posttrade.fill_fetch import HeldPositionSnapshot
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recon.ports import WitnessSnapshot
from tos_runtime.riskstate.held_position import (
    HeldPositionCell,
    HeldPositionConfig,
    HeldPositionProof,
    PositionSide,
    RclTip,
)


class _Clock:
    def __init__(self, now: Callable[[], int], today: Callable[[], str | None]) -> None:
        self.now_ms = now
        self.today = today


class HeldPositionBridge:
    """Correlate a worker snapshot with the RCL revision and one CLOSE proposal."""

    def __init__(
        self,
        *,
        log: SqliteCommitLog,
        now: Callable[[], int],
        today: Callable[[], str | None],
        max_age_ms: int,
    ) -> None:
        self._log = log
        self.cell = HeldPositionCell(
            config=HeldPositionConfig(max_age_ms=max_age_ms),
            clock=_Clock(now, today),
            rcl_tip_reader=self.tip,
            tip_compatible=self.tip_compatible,
        )

    def tip_compatible(self, original: RclTip, current: RclTip) -> bool:
        """Only committed non-reservation approval consumption may advance the tip."""
        try:
            view = self._log.read_approval_only_gap(
                writer_epoch=original.writer_epoch, proof_last_seq=original.last_seq
            )
        except Exception:  # noqa: BLE001 - an unreadable gap cannot authorize a close
            return False
        return (
            view is not None
            and view.epoch == current.writer_epoch
            and view.last_seq == current.last_seq
        )

    def tip(self) -> RclTip | None:
        try:
            epoch = self._log.current_epoch()
            if epoch is None:
                return None
            view = self._log.read_linearizable(writer_epoch=epoch)
            return RclTip(writer_epoch=epoch, last_seq=view.last_seq)
        except Exception:  # noqa: BLE001 - unknown RCL state cannot authorize a close
            return None

    def tip_tuple(self) -> tuple[int, int | None] | None:
        tip = self.tip()
        return None if tip is None else (tip.writer_epoch, tip.last_seq)

    def eligible(self, account: str, instrument: str) -> bool:
        """Only poll for a close over exactly one outstanding consumed entry."""
        try:
            rows = tuple(
                (state, scope)
                for _reservation_id, state, _seq, scope in self._log.reservation_rows()
                if scope.account == account
                and scope.instrument == instrument
                and state is not CapacityState.RELEASED
            )
        except (
            Exception
        ):  # noqa: BLE001 - unreadable capacity never enables a broker read
            return False
        return len(rows) == 1 and rows[0][0] is CapacityState.POSITION_CONSUMED

    def publish(self, result: HeldPositionSnapshot) -> None:
        if (
            result.scope is None
            or result.today is None
            or result.tip is None
            or not isinstance(result.first, WitnessSnapshot)
            or not isinstance(result.confirmation, WitnessSnapshot)
        ):
            self.cell.reject(result.token)
            return
        self.cell.publish(
            result.scope,
            result.first,
            confirming_snapshot=result.confirmation,
            age_origin_ms=result.first_balance_read_started_ms,
            confirming_age_origin_ms=result.confirmation_balance_read_started_ms,
            trading_date=result.today,
            rcl_tip_at_start=RclTip(*result.tip),
            pending_token=result.token,
        )

    def consume(
        self, request: StageRequest, direction: str
    ) -> HeldPositionProof | None:
        tip = self.tip()
        if tip is None or tip.last_seq is None:
            self.cell.invalidate()
            return None
        try:
            side = PositionSide(direction)
        except ValueError:
            self.cell.invalidate()
            return None
        return self.cell.consume_for(
            account=request.instrument_key.account,
            instrument=request.instrument_key.instrument,
            side=side,
            proposal_id=request.proposal.proposal_id,
        )
