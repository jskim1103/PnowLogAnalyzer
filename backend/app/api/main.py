"""Local retrospective analytics API, also serves the built React application."""

import os
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response

from app.database.store import ImportOutcome, Store
from app.domain.cards import nlhe_class, plo5_features
from app.domain.hands import Card, Hand
from app.domain.preflop import GameVariant
from app.equity.calculator import EquityResult, calculate_equity, draw_probability
from app.equity.ranges import RangeEquityResult, WeightedCombo, range_equity
from app.stats.analytics import MetricResult, compute_statistics
from app.stats.registry import REGISTRY, MetricDefinition
from app.strategy.ev import bluff_model, call_ev


class SessionView(BaseModel):
    session_id: str
    owner: str | None
    sources: int
    hands: int
    reconciled: int
    start: str | None
    end: str | None
    reconstruction_version: str


class PlayerView(BaseModel):
    player_id: str
    name: str
    observed_names: list[str]
    sessions: int
    hands: int


class HandSummary(BaseModel):
    session_id: str
    hand_id: str
    number: int
    variant: str
    timestamp: str | None
    players: list[str]
    player_ids: list[str]
    pot: Decimal
    status: str
    diagnostics: int
    board: list[str]


class HandPage(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[HandSummary]


class EquityRequest(BaseModel):
    variant: GameVariant = GameVariant.NLHE
    hands: list[list[str]]
    board: list[str] = Field(default_factory=list)
    method: Literal["exact", "monte_carlo"] = "exact"
    trials: int = Field(default=2000, ge=1, le=10000)
    seed: int = 0


class ComboRequest(BaseModel):
    cards: list[str]
    weight: Decimal = Field(
        default=Decimal(1), gt=0, le=1000000, max_digits=12, decimal_places=6
    )


class RangeRequest(BaseModel):
    ranges: list[list[ComboRequest]]
    board: list[str] = Field(default_factory=list)
    variant: GameVariant = GameVariant.NLHE
    method: Literal["exact", "monte_carlo"] = "exact"
    trials: int = Field(default=2000, ge=1, le=10000)
    seed: int = 0


class CallRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    pot_before_call: Decimal = Field(ge=0)
    call: Decimal = Field(gt=0)
    equity: Decimal = Field(ge=0, le=1)
    rake: Decimal = Field(default=Decimal(0), ge=0)
    closes_betting: bool = True


class BluffRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    pot: Decimal = Field(gt=0)
    bet: Decimal = Field(gt=0)
    fold_probability: Decimal = Field(ge=0, le=1)
    equity_when_called: Decimal = Field(default=Decimal(0), ge=0, le=1)


class DrawRequest(BaseModel):
    unseen: int = Field(ge=0, le=52)
    outs: int = Field(ge=0, le=52)
    draws: int = Field(ge=0, le=5)


class PerformancePoint(BaseModel):
    session_id: str
    hand_id: str
    timestamp: str | None
    net: Decimal
    cumulative: Decimal
    net_bb: Decimal | None
    cumulative_bb: Decimal


class PerformanceView(BaseModel):
    points: list[PerformancePoint]
    excluded: int
    max_drawdown: Decimal
    bb100: Decimal | None


class StartingCell(BaseModel):
    hand_class: str
    observations: int
    voluntary: int
    raised: int
    net: Decimal | None


class StartingView(BaseModel):
    cells: list[StartingCell]
    observed: int
    eligible_dealt: int
    features: list[dict[str, str | int]] = Field(default_factory=list)
    note: str = (
        "Observed NLHE cards only; showdown-selected observations "
        "are not an unbiased dealt range."
    )


def create_app(database: Path | None = None) -> FastAPI:
    app = FastAPI(title="PnowLogAnalyzer", version="0.2.0")
    store = Store(
        database
        or Path(os.environ.get("PNOW_DATABASE", "data/private/analysis.duckdb"))
    )
    app.state.store = store
    trusted = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    }
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(trusted),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def local_origin(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and origin not in trusted:
            return JSONResponse(
                {"detail": "Import/calculation requests require a local origin"},
                status_code=403,
            )
        # Starlette supplies the callable; using its concrete request handler type
        # below avoids leaking arbitrary data into service interfaces.
        return await call_next(request)

    def selected(
        session_id: str | None = None,
        player_id: str | None = None,
        variant: GameVariant | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[Hand, ...]:
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "Start date must not follow end date")
        hands = store.hands(
            session_id=session_id,
            player_id=player_id,
            variant=variant.value if variant else None,
        )
        return tuple(
            h
            for h in hands
            if (
                date_from is None
                or (
                    h.history.timestamp is not None
                    and h.history.timestamp.date() >= date_from
                )
            )
            and (
                date_to is None
                or (
                    h.history.timestamp is not None
                    and h.history.timestamp.date() <= date_to
                )
            )
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.2.0", "analysis": "retrospective"}

    @app.post("/api/import", response_model=ImportOutcome)
    def upload(
        session_id: Annotated[str, Form(min_length=1, max_length=200)],
        files: Annotated[list[UploadFile], File()],
        owner: Annotated[str | None, Form()] = None,
    ) -> ImportOutcome:
        if len(files) > 20:
            raise HTTPException(413, "Maximum 20 files per import")
        with TemporaryDirectory(prefix="pnow-upload-") as temporary:
            paths = []
            total = 0
            for i, file in enumerate(files):
                content = file.file.read(25 * 1024 * 1024 + 1)
                total += len(content)
                if len(content) > 25 * 1024 * 1024 or total > 50 * 1024 * 1024:
                    raise HTTPException(413, "Maximum 25 MB/file and 50 MB/import")
                path = Path(temporary) / f"{i}.csv"
                path.write_bytes(content)
                paths.append(path)
            try:
                return store.import_paths(
                    paths, session_id=session_id, owner=owner or None
                )
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc

    @app.get("/api/sessions", response_model=list[SessionView])
    def sessions() -> list[SessionView]:
        return [SessionView(**row) for row in store.sessions()]

    @app.post("/api/sessions/{session_id}/rebuild", response_model=ImportOutcome)
    def rebuild(session_id: str) -> ImportOutcome:
        try:
            return store.rebuild(session_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/players", response_model=list[PlayerView])
    def players() -> list[PlayerView]:
        names: dict[str, dict[str, tuple[str, int]]] = defaultdict(dict)
        memberships: dict[str, set[str]] = defaultdict(set)
        counts: dict[str, int] = defaultdict(int)
        for report in store.reports():
            timestamps: dict[int, str] = {}
            for record in report.records:
                try:
                    parsed = datetime.fromisoformat(record.at.replace("Z", "+00:00"))
                    timestamps[record.order] = (
                        parsed.astimezone(UTC).isoformat() if parsed.tzinfo else ""
                    )
                except ValueError:
                    timestamps[record.order] = ""
            for player in report.players:
                pid = player.player_id.value
                memberships[pid].add(report.session_id)
                for observation in player.observations:
                    names[pid][observation.display_name] = max(
                        (timestamps.get(observation.order, ""), observation.order),
                        names[pid].get(observation.display_name, ("", -1)),
                    )
        for hand in store.hands():
            for dealt_player in hand.history.players:
                counts[dealt_player.player_id.value] += 1
        return [
            PlayerView(
                player_id=pid,
                name=max(observed, key=lambda name: observed[name]),
                observed_names=sorted(observed),
                sessions=len(memberships[pid]),
                hands=counts[pid],
            )
            for pid, observed in sorted(names.items())
        ]

    @app.get("/api/catalog", response_model=list[MetricDefinition])
    def catalog() -> list[MetricDefinition]:
        return list(REGISTRY.values())

    @app.get("/api/hands", response_model=HandPage)
    def hands(
        session_id: str | None = None,
        player_id: str | None = None,
        variant: GameVariant | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str = "",
        starting_hand: str | None = Query(None, pattern=r"^[2-9TJQKA]{2}[so]?$"),
        min_pot: Decimal | None = Query(None, ge=0),
        max_pot: Decimal | None = Query(None, ge=0),
        sort: Literal["newest", "oldest", "pot_desc", "pot_asc"] = "newest",
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ) -> HandPage:
        hs = selected(session_id, player_id, variant, date_from, date_to)
        if starting_hand and (not player_id or variant != GameVariant.NLHE):
            raise HTTPException(422, "Starting-hand filters require a player and NLHE")
        if min_pot is not None and max_pot is not None and min_pot > max_pot:
            raise HTTPException(422, "Minimum pot exceeds maximum")
        filtered = [
            h
            for h in hs
            if search.casefold() in h.history.hand_id.casefold()
            or search in str(h.history.number)
        ]
        if starting_hand:
            filtered = [
                h
                for h in filtered
                if any(
                    r.player_id.value == player_id
                    and r.complete_hole_cards
                    and nlhe_class(r.observed_cards) == starting_hand
                    for r in h.results
                )
            ]
        filtered = [
            h
            for h in filtered
            if (min_pot is None or sum(p.amount for p in h.pots) >= min_pot)
            and (max_pot is None or sum(p.amount for p in h.pots) <= max_pot)
        ]
        if sort.startswith("pot_"):
            filtered.sort(
                key=lambda h: sum(p.amount for p in h.pots), reverse=sort == "pot_desc"
            )
        elif sort == "newest":
            filtered.reverse()
        items = [
            HandSummary(
                session_id=h.history.session_id,
                hand_id=h.history.hand_id,
                number=h.history.number,
                variant=h.history.variant.value,
                timestamp=h.history.timestamp.isoformat()
                if h.history.timestamp
                else None,
                players=[p.display_name for p in h.history.players],
                player_ids=[p.player_id.value for p in h.history.players],
                pot=sum((p.amount for p in h.pots), Decimal(0)),
                status=h.status,
                diagnostics=len(h.diagnostics),
                board=[c.code for c in h.boards[0].cards] if h.boards else [],
            )
            for h in filtered[offset : offset + limit]
        ]
        return HandPage(total=len(filtered), offset=offset, limit=limit, items=items)

    @app.get("/api/hands/{session_id}/{hand_id}", response_model=Hand)
    def hand_detail(session_id: str, hand_id: str) -> Hand:
        found = next(
            (
                h
                for h in store.hands(session_id=session_id)
                if h.history.hand_id == hand_id
            ),
            None,
        )
        if found is None:
            raise HTTPException(404, "Hand not found")
        return found

    @app.get("/api/stats", response_model=list[MetricResult])
    def stats(
        session_id: str | None = None,
        player_id: str | None = None,
        variant: GameVariant | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        position: str | None = None,
        starting_hand: str | None = Query(None, pattern=r"^[2-9TJQKA]{2}[so]?$"),
        min_stack_bb: float | None = Query(None, ge=0),
        max_stack_bb: float | None = Query(None, ge=0),
    ) -> tuple[MetricResult, ...]:
        if starting_hand and (not player_id or variant != GameVariant.NLHE):
            raise HTTPException(422, "Starting-hand filters require a player and NLHE")
        if (
            min_stack_bb is not None
            and max_stack_bb is not None
            and min_stack_bb > max_stack_bb
        ):
            raise HTTPException(422, "Minimum stack exceeds maximum")
        return compute_statistics(
            selected(session_id, player_id, variant, date_from, date_to),
            player_id=player_id,
            position=position,
            starting_hand=starting_hand,
            min_stack_bb=min_stack_bb,
            max_stack_bb=max_stack_bb,
        )

    @app.get("/api/performance", response_model=PerformanceView)
    def performance(
        player_id: str,
        variant: GameVariant,
        session_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> PerformanceView:
        points = []
        total = Decimal(0)
        total_bb = Decimal(0)
        peak = Decimal(0)
        drawdown = Decimal(0)
        excluded = 0
        valid_bb = 0
        for h in selected(session_id, player_id, variant, date_from, date_to):
            result = next(r for r in h.results if r.player_id.value == player_id)
            if (
                not h.accounting_reconciled
                or not h.action_consistent
                or result.net is None
            ):
                excluded += 1
                continue
            total += result.net
            net_bb = result.net / h.big_blind if h.big_blind else None
            if net_bb is not None:
                valid_bb += 1
                total_bb += net_bb
            peak = max(peak, total)
            drawdown = max(drawdown, peak - total)
            points.append(
                PerformancePoint(
                    session_id=h.history.session_id,
                    hand_id=h.history.hand_id,
                    timestamp=h.history.timestamp.isoformat()
                    if h.history.timestamp
                    else None,
                    net=result.net,
                    cumulative=total,
                    net_bb=net_bb,
                    cumulative_bb=total_bb,
                )
            )
        return PerformanceView(
            points=points,
            excluded=excluded,
            max_drawdown=drawdown,
            bb100=total_bb / valid_bb * 100 if valid_bb else None,
        )

    @app.get("/api/starting-hands", response_model=StartingView)
    def starting(
        player_id: str,
        session_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        variant: GameVariant = GameVariant.NLHE,
    ) -> StartingView:
        groups: dict[str, list[tuple[bool, bool, Decimal | None]]] = defaultdict(list)
        feature_counts: dict[tuple[str, str], int] = defaultdict(int)
        observed = 0
        eligible = 0
        for h in selected(session_id, player_id, variant, date_from, date_to):
            eligible += 1
            result = next(r for r in h.results if r.player_id.value == player_id)
            if not result.complete_hole_cards or not h.action_consistent:
                continue
            observed += 1
            if variant == GameVariant.PLO5:
                for name, value in plo5_features(result.observed_cards).items():
                    feature_counts[name, value] += 1
                continue
            category = nlhe_class(result.observed_cards)
            pre = [
                d
                for d in h.decisions
                if d.street.value == "preflop" and d.event.player_id == result.player_id
            ]
            vpip = any(d.event.kind.value in {"call", "raise"} for d in pre)
            pfr = any(d.event.kind.value == "raise" for d in pre)
            groups[category].append((vpip, pfr, result.net))
        cells = [
            StartingCell(
                hand_class=category,
                observations=len(values),
                voluntary=sum(v[0] for v in values),
                raised=sum(v[1] for v in values),
                net=sum((v[2] for v in values if v[2] is not None), Decimal(0))
                if all(v[2] is not None for v in values)
                else None,
            )
            for category, values in sorted(groups.items())
        ]
        return StartingView(
            cells=cells,
            observed=observed,
            eligible_dealt=eligible,
            features=[
                {"feature": name, "value": value, "observations": count}
                for (name, value), count in sorted(feature_counts.items())
            ],
            note=(
                "Observed cards only; showdown-selected observations "
                "are not an unbiased dealt range."
            ),
        )

    @app.post("/api/equity", response_model=EquityResult)
    def equity(body: EquityRequest) -> EquityResult:
        try:
            return calculate_equity(
                tuple(tuple(Card(c) for c in hand) for hand in body.hands),
                tuple(Card(c) for c in body.board),
                body.variant,
                method=body.method,
                trials=body.trials,
                seed=body.seed,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/range-equity", response_model=RangeEquityResult)
    def ranges(body: RangeRequest) -> RangeEquityResult:
        try:
            return range_equity(
                tuple(
                    tuple(
                        WeightedCombo(tuple(Card(c) for c in combo.cards), combo.weight)
                        for combo in player_range
                    )
                    for player_range in body.ranges
                ),
                tuple(Card(c) for c in body.board),
                body.variant,
                method=body.method,
                trials=body.trials,
                seed=body.seed,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/call-ev", response_model=dict[str, Decimal])
    def odds(body: CallRequest) -> dict[str, Decimal]:
        try:
            return call_ev(**body.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/bluff-ev", response_model=dict[str, Decimal])
    def bluff(body: BluffRequest) -> dict[str, Decimal]:
        return bluff_model(**body.model_dump())

    @app.post("/api/draw-probability", response_model=dict[str, float | str])
    def draws(body: DrawRequest) -> dict[str, float | str]:
        try:
            result = draw_probability(body.unseen, body.outs, body.draws)
            return {"probability": float(result), "exact": str(result)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    frontend = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


def serve() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
