"""Timer-based watcher for automatic dosing totals."""

# ruff: noqa: D107,E501

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_time

from ...common.notification_poll import (
    NotificationPollPayload,
    async_poll_device_notifications,
    async_track_notification_poll,
)
from ...const import DOMAIN
from ...models import ChihirosData
from ...runtime import DosingChihirosClient
from .protocol import schedule_disable_frames
from .storage import DoserExtStore, async_store_for_device, update_signal

_LOGGER = logging.getLogger(__name__)

BASELINE_LEAD_SECONDS = 150.0
RESULT_DELAY_SECONDS = 150.0
PAST_WINDOW_SECONDS = 7200.0
TOTALS_MODE = 0x1E
NOTIFICATION_TOTALS_MODE = 0x22
TIMER_STATUS_DATA = f"{DOMAIN}_doser_ext_timer_status"
TIMER_STATUS_SIGNAL = f"{DOMAIN}_doser_ext_timer_status_updated"


def timer_status_signal(address: str) -> str:
    """Return dispatcher signal for one dosing timer status sensor."""
    return f"{TIMER_STATUS_SIGNAL}_{address.lower()}"


def timer_status_for_hass(hass: HomeAssistant, address: str) -> dict[str, Any]:
    """Return current timer status for one dosing device."""
    return dict(hass.data.get(TIMER_STATUS_DATA, {}).get(address.upper(), {}))


class DoserAutoTotalsWatcher:
    """Watch local schedules and read device auto totals after due runs."""

    def __init__(self, hass: HomeAssistant, chihiros_data: ChihirosData) -> None:
        self.hass = hass
        self._chihiros_data = chihiros_data
        self._device = chihiros_data.device
        self._task: asyncio.Task | None = None
        self._store: DoserExtStore | None = None
        self._unsub_dispatcher: Callable[[], None] | None = None
        self._unsub_notification_poll: Callable[[], None] | None = None
        self._unsub_timers: list[Callable[[], None]] = []
        self._checked: set[tuple[int, str, int]] = set()
        self._baselines: dict[tuple[int, str, int], list[float]] = {}
        self._safety_disabled: set[int] = set()
        self._totals_read_lock = asyncio.Lock()
        self._totals_snapshots: dict[tuple[str, str], tuple[list[float] | None, str]] = {}
        self._failed_snapshots_logged: set[tuple[str, str]] = set()
        self._last_read_error = ""
        self._last_raw_notifications: list[bytes] = []
        self._reschedule_task: asyncio.Task | None = None
        self._started = False
        self._status: dict[str, Any] = {
            "state": "starting",
            "planned_baselines": 0,
            "planned_results": 0,
            "due_results": 0,
        }

    def start(self) -> None:
        """Start the background watcher."""
        if self._started:
            return
        self._started = True
        self._task = self.hass.create_task(self._async_start())

    async def stop(self) -> None:
        """Stop the background watcher."""
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None
        if self._unsub_notification_poll is not None:
            self._unsub_notification_poll()
            self._unsub_notification_poll = None
        self._clear_timers()
        if self._reschedule_task is not None:
            self._reschedule_task.cancel()
            self._reschedule_task = None
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._started = False
        self._set_status("stopped")

    def _set_status(self, state: str, **attrs: Any) -> None:
        """Publish timer status for the diagnostic sensor."""
        self._status.update(attrs)
        self._status["state"] = state
        self._status["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        self.hass.data.setdefault(TIMER_STATUS_DATA, {})[self._device.address.upper()] = dict(self._status)
        async_dispatcher_send(self.hass, timer_status_signal(self._device.address))

    async def _async_start(self) -> None:
        """Load state and install timer callbacks."""
        pump_count = self._chihiros_data.dosing_totals.pump_count if self._chihiros_data.dosing_totals else 4
        self._store = await async_store_for_device(self.hass, self._device.address, pump_count)
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, update_signal(self._device.address), self._request_reschedule
        )
        _LOGGER.debug("Starting Chihiros Doser auto-total timer watcher for %s", self._device.address)
        self._set_status("starting")
        self._unsub_notification_poll = async_track_notification_poll(self.hass, self._async_poll_notifications)
        try:
            await self._reschedule()
        except Exception as ex:  # noqa: BLE001
            _LOGGER.exception(
                "Chihiros Doser scheduler setup failed for %s; notification polling remains active",
                self._device.address,
            )
            self._set_status("timer fehler", last_error=f"{type(ex).__name__}: {ex}")
        await self._async_poll_notifications(datetime.now().astimezone())

    async def _async_poll_notifications(self, _now: datetime) -> None:
        """Read the Doser notification burst every 15 minutes and record its result."""
        if self._store is None:
            return
        checked_at = datetime.now().astimezone()
        self._set_status("meldung liest", last_notification_started_at=checked_at.isoformat(timespec="seconds"))

        async def _query() -> NotificationPollPayload:
            values = await self._read_device_notification_burst()
            detail = ", ".join(f"CH{idx + 1} {value:.1f} mL" for idx, value in enumerate(values or []))
            return NotificationPollPayload(
                success=values is not None,
                raw_frames=tuple(self._last_raw_notifications),
                values=tuple(values or ()),
                output=detail,
                error=self._last_read_error,
            )

        result = await async_poll_device_notifications(
            self.hass,
            address=self._device.address,
            device_type="doser",
            mode=NOTIFICATION_TOTALS_MODE,
            expected_modes=(0x0A, 0xFE, 0x1E, 0x22),
            query=_query,
        )
        values = list(result.values)
        checked_at = result.checked_at
        if result.status == "ok":
            await self._store.async_set_auto_daily_values(values, mode=NOTIFICATION_TOTALS_MODE)
            await self._store.async_record_notification_poll(
                "ok",
                result.output,
                values,
                mode=NOTIFICATION_TOTALS_MODE,
                raw_frames=list(result.raw_frames),
            )
            self._set_status(
                "meldung ok",
                last_notification_status="ok",
                last_notification_at=checked_at.isoformat(timespec="seconds"),
                last_notification_values=values,
                last_notification_frames=[frame.hex(" ").upper() for frame in result.raw_frames],
                last_notification_error="",
            )
            return
        error = result.error
        await self._store.async_record_notification_poll(
            "error",
            error,
            mode=NOTIFICATION_TOTALS_MODE,
            raw_frames=list(result.raw_frames),
        )
        self._set_status(
            "meldung fehler",
            last_notification_status="error",
            last_notification_at=checked_at.isoformat(timespec="seconds"),
            last_notification_values=[],
            last_notification_frames=[frame.hex(" ").upper() for frame in result.raw_frames],
            last_notification_error=error,
        )

    async def _read_device_notification_burst(self) -> list[float] | None:
        """Collect the app-like Runtime, status and Doser totals notification burst."""
        async with self._totals_read_lock:
            dosing_device = cast(DosingChihirosClient, self._device)
            dosing_device.raw_notifications.clear()
            dosing_device.last_doser_totals = None
            self._last_raw_notifications = []
            try:
                await dosing_device.read_doser_notifications(notification_wait=5.0)
                self._last_read_error = ""
                return dosing_device.last_doser_totals
            except Exception as ex:
                self._last_read_error = str(ex)
                _LOGGER.warning(
                    "Chihiros Doser Meldungen fuer %s konnten nicht gelesen werden: %s",
                    self._device.address,
                    ex,
                )
                return None
            finally:
                self._last_raw_notifications = [bytes(frame) for frame in dosing_device.raw_notifications]

    def _request_reschedule(self) -> None:
        """Schedule one timer rebuild after store updates."""
        if self._reschedule_task is None or self._reschedule_task.done():
            self._reschedule_task = self.hass.create_task(self._delayed_reschedule())

    async def _delayed_reschedule(self) -> None:
        await asyncio.sleep(0.25)
        await self._reschedule()

    def _clear_timers(self) -> None:
        while self._unsub_timers:
            self._unsub_timers.pop()()

    async def _reschedule(self) -> None:
        """Rebuild all baseline/result timers from the local schedule table."""
        if self._store is None:
            return
        self._clear_timers()
        await self._store.async_load()
        await self._disable_over_limit_rows()
        rows = self._store.schedule_rows()
        now = datetime.now().astimezone()
        planned_baselines = 0
        planned_results = 0
        due_results = 0
        next_baseline: datetime | None = None
        next_result: datetime | None = None

        for run_at, row in _candidate_schedule_runs(rows, days_back=1, days_forward=2):
            if not bool(row.get("enabled")):
                continue
            marker = (int(row.get("channel", -1)), run_at.isoformat(), TOTALS_MODE)
            if marker in self._checked:
                continue
            baseline_at = run_at - timedelta(seconds=BASELINE_LEAD_SECONDS)
            result_at = run_at + timedelta(seconds=RESULT_DELAY_SECONDS)
            if baseline_at <= now < run_at and marker not in self._baselines:
                self.hass.create_task(self._handle_baseline(run_at, row))
            elif baseline_at > now:
                self._unsub_timers.append(
                    async_track_point_in_time(self.hass, self._baseline_callback(run_at, row), baseline_at)
                )
                planned_baselines += 1
                if next_baseline is None or baseline_at < next_baseline:
                    next_baseline = baseline_at
            if result_at <= now and (now - result_at).total_seconds() <= PAST_WINDOW_SECONDS:
                self.hass.create_task(self._handle_result(run_at, row))
                due_results += 1
            elif result_at > now:
                self._unsub_timers.append(
                    async_track_point_in_time(self.hass, self._result_callback(run_at, row), result_at)
                )
                planned_results += 1
                if next_result is None or result_at < next_result:
                    next_result = result_at

        state = "geplant" if planned_baselines or planned_results else ("faellig" if due_results else "kein timer")
        self._set_status(
            state,
            planned_baselines=planned_baselines,
            planned_results=planned_results,
            due_results=due_results,
            next_baseline=next_baseline.isoformat(timespec="seconds") if next_baseline else None,
            next_result=next_result.isoformat(timespec="seconds") if next_result else None,
            active_timers=len(self._unsub_timers),
        )
        _LOGGER.debug(
            "Chihiros Doser auto-total timers for %s: %s baseline, %s result, %s due",
            self._device.address,
            planned_baselines,
            planned_results,
            due_results,
        )

    def _baseline_callback(self, run_at: datetime, row: dict[str, Any]) -> Callable[[datetime], None]:
        def _callback(_now: datetime) -> None:
            self.hass.create_task(self._handle_baseline(run_at, row))

        return _callback

    def _result_callback(self, run_at: datetime, row: dict[str, Any]) -> Callable[[datetime], None]:
        def _callback(_now: datetime) -> None:
            self.hass.create_task(self._handle_result(run_at, row))

        return _callback

    async def _handle_baseline(self, run_at: datetime, row: dict[str, Any]) -> None:
        marker = (int(row.get("channel", -1)), run_at.isoformat(), TOTALS_MODE)
        if marker in self._baselines or marker in self._checked:
            return
        channel = int(row.get("channel", -1))
        _LOGGER.debug(
            "Reading Chihiros Doser baseline CH%s before auto run at %s",
            channel + 1,
            run_at.isoformat(),
        )
        self._set_status(
            "baseline liest", last_baseline_run=run_at.isoformat(timespec="seconds"), last_channel=channel + 1
        )
        values = await self._read_device_totals(("baseline", run_at.isoformat()))
        if not values:
            await self._record_read_failure_once("vorher", run_at, channel)
            self._set_status(
                "baseline fehler",
                last_baseline_run=run_at.isoformat(timespec="seconds"),
                last_channel=channel + 1,
                last_error=self._last_read_error,
            )
            return
        if values:
            self._baselines[marker] = values
            if self._store is not None:
                await self._store.async_set_auto_daily_values(values, mode=TOTALS_MODE)
                await self._store.async_record_auto_total_checkpoint(
                    "vorher",
                    values,
                    mode=TOTALS_MODE,
                    channel=channel if channel >= 0 else None,
                    run_at=run_at,
                )
            self._set_status(
                "baseline ok",
                last_baseline_run=run_at.isoformat(timespec="seconds"),
                last_baseline_at=(run_at - timedelta(seconds=BASELINE_LEAD_SECONDS)).isoformat(timespec="seconds"),
                last_values=values,
            )

    async def _handle_result(self, run_at: datetime, row: dict[str, Any]) -> None:
        if self._store is None:
            return
        marker = (int(row.get("channel", -1)), run_at.isoformat(), TOTALS_MODE)
        if marker in self._checked:
            return
        self._checked.add(marker)
        channel = int(row.get("channel", -1))
        _LOGGER.debug(
            "Reading Chihiros Doser result CH%s after auto run at %s",
            channel + 1,
            run_at.isoformat(),
        )
        self._set_status(
            "resultat liest", last_result_run=run_at.isoformat(timespec="seconds"), last_channel=channel + 1
        )
        success = await self._read_and_store_totals(
            self._store,
            baseline=self._baselines.pop(marker, None),
            run_at=run_at,
            channel=channel if channel >= 0 else None,
        )
        if success:
            await self._store.async_add_log(
                "Scheduler erfolgreich",
                channel if channel >= 0 else None,
                f"ausgefuehrt um {run_at.isoformat(timespec='minutes')}",
            )
            if channel >= 0:
                await self._disable_schedule_if_auto_limit_reached(channel)
            self._set_status(
                "resultat ok", last_result_run=run_at.isoformat(timespec="seconds"), last_channel=channel + 1
            )
        else:
            await self._record_read_failure_once("nachher", run_at, channel)
            self._set_status(
                "resultat fehler",
                last_result_run=run_at.isoformat(timespec="seconds"),
                last_channel=channel + 1,
                last_error=self._last_read_error,
            )
        self._request_reschedule()

    async def _read_and_store_totals(
        self,
        store: DoserExtStore,
        *,
        baseline: list[float] | None,
        run_at: datetime,
        channel: int | None,
    ) -> bool:
        values = await self._read_device_totals(("result", run_at.isoformat()))
        if not values:
            return False
        await store.async_set_auto_daily_values(values, mode=TOTALS_MODE)
        await store.async_record_auto_total_checkpoint(
            "nachher",
            values,
            mode=TOTALS_MODE,
            channel=channel,
            run_at=run_at,
        )
        if baseline is not None:
            await store.async_apply_auto_daily_delta(
                baseline,
                values,
                mode=TOTALS_MODE,
                channel=channel,
                run_at=run_at,
            )
        return True

    async def _read_device_totals(self, snapshot_key: tuple[str, str] | None = None) -> list[float] | None:
        async with self._totals_read_lock:
            if snapshot_key is not None and snapshot_key in self._totals_snapshots:
                cached_result, cached_error = self._totals_snapshots[snapshot_key]
                self._last_read_error = cached_error
                return cached_result
            dosing_device = cast(DosingChihirosClient, self._device)
            self._last_raw_notifications = []
            try:
                values = await dosing_device.read_auto_totals(mode=TOTALS_MODE)
                if values is None:
                    values = await dosing_device.read_auto_totals_via_dialog(mode=TOTALS_MODE)
                self._last_read_error = ""
                result = values or None
            except Exception as ex:
                self._last_read_error = str(ex)
                _LOGGER.warning(
                    "Chihiros Doser Tageswerte fuer %s konnten nicht gelesen werden: %s",
                    self._device.address,
                    ex,
                )
                result = None
            finally:
                self._last_raw_notifications = [
                    bytes(frame) for frame in getattr(dosing_device, "raw_notifications", [])
                ]
            if snapshot_key is not None:
                self._totals_snapshots[snapshot_key] = (result, self._last_read_error)
                while len(self._totals_snapshots) > 100:
                    self._totals_snapshots.pop(next(iter(self._totals_snapshots)))
            return result

    async def _record_read_failure_once(self, label: str, run_at: datetime, channel: int) -> None:
        """Store one readable failure for a shared device snapshot."""
        key = (str(label), run_at.isoformat())
        if key in self._failed_snapshots_logged or self._store is None:
            return
        self._failed_snapshots_logged.add(key)
        await self._store.async_record_auto_total_read_failure(
            label,
            self._last_read_error or "Keine Tageswerte vom Geraet empfangen",
            channel=channel if channel >= 0 else None,
            run_at=run_at,
        )

    async def _disable_over_limit_rows(self) -> None:
        """Disable already over-limit schedules before rebuilding timers."""
        if self._store is None:
            return
        for row in self._store.schedule_rows():
            if not bool(row.get("enabled")):
                continue
            try:
                channel = int(row.get("channel", -1))
            except (TypeError, ValueError):
                continue
            if channel >= 0:
                await self._disable_schedule_if_auto_limit_reached(channel)

    async def _disable_schedule_if_auto_limit_reached(self, channel: int) -> None:
        """Send a disable command when the automatic daily limit is reached."""
        if self._store is None or channel in self._safety_disabled:
            return
        safety = self._store.doser_safety_limits()
        limit = float(safety.get("max_auto_ml", 0.0))
        if limit <= 0:
            return
        auto_today = self._store.auto_daily_ml(channel)
        if auto_today < limit:
            return
        self._safety_disabled.add(channel)
        detail = f"Automatisch heute {auto_today:.1f} mL >= Limit {limit:.1f} mL"
        try:
            frames = schedule_disable_frames(self._device.get_next_msg_id, channel)
            await self._send_extension_frames(frames)
            await self._store.async_disable_schedule_for_safety(channel)
            await self._store.async_add_log(
                "Ueberdosierungsschutz",
                channel,
                f"{detail}; Scheduler am Geraet deaktiviert",
            )
            self._set_status("schutz deaktiviert", last_channel=channel + 1, last_safety_detail=detail)
        except Exception as ex:
            await self._store.async_add_log(
                "Ueberdosierungsschutz FAIL",
                channel,
                f"{detail}; Scheduler am Geraet nicht deaktiviert: {ex}",
            )
            self._set_status("schutz fehler", last_channel=channel + 1, last_safety_detail=str(ex))

    async def _send_extension_frames(self, frames: list[bytearray]) -> None:
        """Send dosing extension frames through the integration device transport."""
        send_command = getattr(self._device, "_send_command", None)
        if send_command is None:
            raise RuntimeError(f"{self._device.name} cannot send raw dosing extension frames")
        ensure_connected = getattr(self._device, "_ensure_connected", None)
        send_while_connected = getattr(self._device, "_send_command_while_connected", None)
        disconnect = getattr(self._device, "_execute_disconnect", None)
        if ensure_connected is None or send_while_connected is None or disconnect is None:
            await send_command(frames, 3)
            return
        await ensure_connected()
        try:
            for frame in frames:
                await send_while_connected([bytes(frame)], 3)
                await asyncio.sleep(0.15)
        finally:
            await disconnect()


def _weekday_bit_for_date(value: datetime) -> int:
    return [64, 32, 16, 8, 4, 2, 1][value.weekday()]


def _candidate_schedule_runs(
    rows: list[dict[str, Any]],
    *,
    days_back: int = 1,
    days_forward: int = 1,
) -> list[tuple[datetime, dict[str, Any]]]:
    now = datetime.now().astimezone()
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for row in rows:
        if not bool(row.get("enabled")):
            continue
        schedule_kind = str(row.get("schedule_kind") or "single_dose")
        try:
            hour_text, minute_text = str(row["schedule_time"]).split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
        except (KeyError, ValueError):
            continue
        weekdays_mask = int(row.get("weekdays_mask", 0))
        valid_from_tomorrow = bool(int(row.get("valid_from_tomorrow") or 0))
        updated_at = None
        if valid_from_tomorrow:
            try:
                updated_at = datetime.fromisoformat(
                    str(row.get("updated_at") or "").replace("Z", "+00:00")
                ).astimezone()
            except ValueError:
                updated_at = now
        for day_offset in range(-days_back, days_forward + 1):
            day = now + timedelta(days=day_offset)
            if valid_from_tomorrow and updated_at is not None and day.date() <= updated_at.date():
                continue
            if not (weekdays_mask & _weekday_bit_for_date(day)):
                continue
            if schedule_kind == "interval":
                _add_interval_candidates(candidates, row, day, hour, minute)
            elif schedule_kind == "timer":
                _add_timer_candidates(candidates, row, day, hour, minute)
            elif schedule_kind == "window":
                _add_window_candidates(candidates, row, day, hour, minute)
            else:
                candidates.append((day.replace(hour=hour, minute=minute, second=0, microsecond=0), row))
    return candidates


def _add_interval_candidates(
    candidates: list[tuple[datetime, dict[str, Any]]],
    row: dict[str, Any],
    day: datetime,
    hour: int,
    minute: int,
) -> None:
    updated_raw = str(row.get("updated_at") or "")
    try:
        updated_at = datetime.fromisoformat(updated_raw.replace("Z", "+00:00")).astimezone()
    except ValueError:
        updated_at = None
    if updated_at is not None and day.date() < updated_at.date():
        return
    interval_minutes = max(1, min(59, minute if minute > 0 else 1))
    midnight = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = midnight + timedelta(days=1)
    seen: set[datetime] = set()

    def add_candidate(value: datetime) -> None:
        candidate_at = value.replace(second=0, microsecond=0)
        if updated_at is not None and candidate_at <= updated_at:
            return
        if candidate_at in seen:
            return
        seen.add(candidate_at)
        candidates.append((candidate_at, row))

    candidate = midnight + timedelta(minutes=interval_minutes)
    while candidate < end_of_day:
        add_candidate(candidate)
        candidate += timedelta(minutes=interval_minutes)


def _add_timer_candidates(
    candidates: list[tuple[datetime, dict[str, Any]]], row: dict[str, Any], day: datetime, hour: int, minute: int
) -> None:
    entries = row.get("entries") or []
    if isinstance(entries, list) and entries:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                entry_hour = int(entry.get("hour", hour))
                entry_minute = int(entry.get("minute", minute))
            except (TypeError, ValueError):
                continue
            candidates.append((day.replace(hour=entry_hour, minute=entry_minute, second=0, microsecond=0), row))
        return
    candidates.append((day.replace(hour=hour, minute=minute, second=0, microsecond=0), row))


def _add_window_candidates(
    candidates: list[tuple[datetime, dict[str, Any]]], row: dict[str, Any], day: datetime, hour: int, minute: int
) -> None:
    entries = row.get("entries") or []
    if not isinstance(entries, list) or not entries:
        candidates.append((day.replace(hour=hour, minute=minute, second=0, microsecond=0), row))
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            entry_hour = int(entry.get("start_hour", hour))
            entry_minute = int(entry.get("start_minute", minute))
            end_hour = int(entry.get("end_hour", entry_hour))
            end_minute = int(entry.get("end_minute", entry_minute))
            dose_count = max(1, min(24, int(entry.get("value", 1) or 1)))
        except (TypeError, ValueError):
            continue
        start_at = day.replace(hour=entry_hour, minute=entry_minute, second=0, microsecond=0)
        end_at = day.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        if end_at < start_at:
            end_at += timedelta(days=1)
        if dose_count == 1:
            candidates.append((start_at, row))
            continue
        duration_s = (end_at - start_at).total_seconds()
        seen: set[datetime] = set()
        for index in range(dose_count):
            candidate = (start_at + timedelta(seconds=round(duration_s * index / (dose_count - 1)))).replace(
                second=0, microsecond=0
            )
            if candidate not in seen:
                candidates.append((candidate, row))
                seen.add(candidate)
