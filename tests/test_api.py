from app.api.main import create_app
from fastapi.testclient import TestClient
from test_hand_adapter import END, STACKS, START
from test_importer import export


def input_file(tmp_path):
    return export(
        tmp_path,
        list(
            enumerate(
                [
                    START,
                    STACKS,
                    '"Alpha 🐣 @ synthetic_a" posts a small blind of 0.25',
                    '"Beta @ synthetic_b" posts a big blind of 0.50',
                    '"Alpha 🐣 @ synthetic_a" calls 0.50',
                    '"Beta @ synthetic_b" checks',
                    "Flop:  [2♣, 3♦, 4♥]",
                    '"Beta @ synthetic_b" checks',
                    '"Alpha 🐣 @ synthetic_a" bets 1.00',
                    '"Beta @ synthetic_b" folds',
                    'Uncalled bet of 1.00 returned to "Alpha 🐣 @ synthetic_a"',
                    '"Alpha 🐣 @ synthetic_a" collected 1.00 from pot',
                    END,
                ],
                1,
            )
        ),
    )


def test_full_csv_api_storage_catalog_replay_and_analytics(tmp_path):
    app = create_app(tmp_path / "api.duckdb")
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/players").json() == []
        path = input_file(tmp_path)
        for new_records in (13, 0):
            response = client.post(
                "/api/import",
                data={"session_id": "s"},
                files={"files": ("synthetic.csv", path.read_bytes(), "text/csv")},
            )
            assert response.status_code == 200, response.text
            assert response.json()["new_records"] == new_records
            assert response.json()["reconciled"] == 1
            assert response.json()["warnings"] == 1  # Explicit dead button.
        assert len(client.get("/api/players").json()) == 2
        assert client.get("/api/sessions").json()[0]["hands"] == 1
        assert len(client.get("/api/catalog").json()) >= 60
        listing = client.get("/api/hands?limit=1").json()
        assert listing["total"] == 1
        detail = client.get("/api/hands/s/synthetic-hand").json()
        assert len(detail["decisions"]) == 5
        assert detail["accounting_reconciled"]
        assert detail["results"][0]["ending_stack"] == "50.50"
        stats = client.get("/api/stats?player_id=synthetic_a&variant=PLO5").json()
        vpip = next(row for row in stats if row["metric_id"] == "preflop.vpip")
        assert vpip["value"] == "1" and vpip["denominator"] == 1
        performance = client.get(
            "/api/performance?player_id=synthetic_a&variant=PLO5"
        ).json()
        assert performance["points"][0]["cumulative"] == "0.50"
        assert (
            client.get("/api/starting-hands?player_id=synthetic_a").json()["observed"]
            == 0
        )
        assert client.get("/api/hands?variant=bad").status_code == 422
        assert client.get("/api/hands?offset=-1").status_code == 422
        assert (
            client.get("/api/stats?min_stack_bb=10&max_stack_bb=5").status_code == 422
        )
        assert client.get("/api/hands/s/missing").status_code == 404
    with TestClient(create_app(tmp_path / "api.duckdb")) as reopened:
        assert reopened.get("/api/hands").json()["total"] == 1


def test_math_endpoints_validation_and_local_origin(tmp_path):
    with TestClient(create_app(tmp_path / "api.duckdb")) as client:
        result = client.post(
            "/api/equity",
            json={
                "hands": [["Ac", "Ad"], ["Kc", "Kd"]],
                "board": ["2s", "3h", "7c", "9h"],
                "variant": "NLHE",
            },
        )
        assert result.status_code == 200, result.text
        assert result.json()["equities"][0] == 42 / 44
        assert (
            client.post(
                "/api/equity", json={"hands": [["Ac", "Ad"], ["Ac", "Kd"]]}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/call-ev", json={"pot_before_call": 100, "call": 50, "equity": 0.4}
            ).json()["call_ev"]
            == "10.0"
        )
        assert (
            client.post(
                "/api/call-ev", json={"pot_before_call": 100, "call": -1, "equity": 0.4}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/draw-probability", json={"unseen": 47, "outs": 9, "draws": 1}
            ).json()["exact"]
            == "9/47"
        )
        assert (
            client.post(
                "/api/import", headers={"Origin": "https://untrusted.example"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/import",
                data={"session_id": "s"},
                files={"files": ("bad.csv", b"bad")},
            ).status_code
            == 409
        )


def test_range_math_and_observed_starting_hand_filters(tmp_path):
    import csv

    with TestClient(create_app(tmp_path / "api.duckdb")) as client:
        request = {
            "variant": "NLHE",
            "board": ["3h", "4c", "7d", "9s", "Tc"],
            "ranges": [
                [
                    {"cards": ["Ah", "Ad"], "weight": 3},
                    {"cards": ["2c", "2d"], "weight": 1},
                ],
                [{"cards": ["Kc", "Kd"], "weight": 1}],
            ],
        }
        response = client.post("/api/range-equity", json=request)
        assert response.status_code == 200, response.text
        assert response.json()["equities"] == [0.75, 0.25]
        source = input_file(tmp_path)
        with source.open(newline="", encoding="utf-8") as file:
            rows = list(csv.reader(file))
        rows[1][0] = rows[1][0].replace(
            "Pot Limit Omaha 5 Hi", "No Limit Texas Hold'em"
        )
        rows.insert(-1, ['"Alpha 🐣 @ synthetic_a" shows a A♣, A♦.', rows[1][1], "12"])
        rows[-2][2] = "13"
        rows[-1][2] = "14"
        with source.open("w", newline="", encoding="utf-8") as file:
            csv.writer(file).writerows(rows)
        assert (
            client.post(
                "/api/import",
                data={"session_id": "s"},
                files={"files": ("s.csv", source.read_bytes())},
            ).status_code
            == 200
        )
        for endpoint in ("hands", "stats"):
            response = client.get(
                "/api/"
                + endpoint
                + "?player_id=synthetic_a&variant=NLHE&starting_hand=AA"
            )
            assert response.status_code == 200, response.text
            if endpoint == "hands":
                assert response.json()["total"] == 1
            else:
                assert (
                    next(
                        row
                        for row in response.json()
                        if row["metric_id"] == "preflop.vpip"
                    )["denominator"]
                    == 1
                )
        assert (
            client.get(
                "/api/hands?player_id=synthetic_a&variant=NLHE&starting_hand=KK"
            ).json()["total"]
            == 0
        )
        assert client.get("/api/hands?starting_hand=AA").status_code == 422
        assert (
            client.get("/api/starting-hands?player_id=synthetic_a&variant=NLHE").json()[
                "observed"
            ]
            == 1
        )


def test_primary_name_uses_timestamp_across_sessions_not_session_local_order(tmp_path):
    from app.database.store import Store

    database = tmp_path / "api.duckdb"
    old = export(
        tmp_path, [(100, 'The player "Old name @ stable-id" requested a seat.')]
    )
    recent = export(
        tmp_path, [(1, 'The player "New 🐣 @ stable-id" requested a seat.')], "new.csv"
    )
    recent.write_text(recent.read_text().replace("2026-01-01", "2027-01-01"))
    store = Store(database)
    store.import_paths([old], session_id="old")
    store.import_paths([recent], session_id="recent")
    with TestClient(create_app(database)) as client:
        player = client.get("/api/players").json()[0]
        assert player["name"] == "New 🐣"
        assert player["observed_names"] == ["New 🐣", "Old name"]
        assert player["sessions"] == 2
