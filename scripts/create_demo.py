"""Generate an explicitly synthetic, independently accounted CSV for UI practice.

Run with Python 3.12 from the repository root. Nothing is imported automatically.
"""

import csv
from decimal import Decimal
from pathlib import Path


def create_demo(path: Path) -> None:
    names = {"a": "River 🐣 @ demo-a", "b": "Orbit @ demo-b"}
    stacks = {"a": Decimal(50), "b": Decimal(50)}
    entries: list[tuple[str, str, int]] = []
    sequence = 1
    for number in range(1, 5):
        button = "a" if number % 2 else "b"
        other = "b" if button == "a" else "a"
        a, b = names[button], names[other]
        lines = [
            f"-- starting hand #{number} (id: demo-hand-{number})  "
            f'No Limit Texas Hold\'em (dealer: "{a}") --',
            f'Player stacks: #1 "{names["a"]}" ({stacks["a"]:.2f}) | '
            f'#9 "{names["b"]}" ({stacks["b"]:.2f})',
            f'"{a}" posts a small blind of 0.25',
            f'"{b}" posts a big blind of 0.50',
        ]
        if number in {1, 2}:
            lines += [
                f'"{a}" raises to 1.50',
                f'"{b}" calls 1.50',
                "Flop:  [2♣, 3♦, 4♥]",
                f'"{b}" checks',
                f'"{a}" bets 1.00',
                f'"{b}" folds',
                f'Uncalled bet of 1.00 returned to "{a}"',
                f'"{a}" collected 3.00 from pot',
                f'"{a}" shows a A♣, A♦.',
            ]
            stacks[button] += Decimal("1.50")
            stacks[other] -= Decimal("1.50")
        elif number == 3:
            lines += [
                f'"{a}" folds',
                f'Uncalled bet of 0.25 returned to "{b}"',
                f'"{b}" collected 0.50 from pot',
            ]
            stacks[button] -= Decimal(".25")
            stacks[other] += Decimal(".25")
        else:
            lines += [
                f'"{a}" calls 0.50',
                f'"{b}" checks',
                "Flop:  [2♣, 3♦, 4♥]",
                f'"{b}" checks',
                f'"{a}" checks',
                "Turn: 2♣, 3♦, 4♥ [5♠]",
                f'"{b}" bets 1.00',
                f'"{a}" calls 1.00',
                "River: 2♣, 3♦, 4♥, 5♠ [9♣]",
                f'"{b}" bets 2.00',
                f'"{a}" folds',
                f'Uncalled bet of 2.00 returned to "{b}"',
                f'"{b}" collected 3.00 from pot',
            ]
            stacks[button] -= Decimal("1.50")
            stacks[other] += Decimal("1.50")
        lines.append(f"-- ending hand #{number} --")
        for line in lines:
            entries.append((line, f"2026-01-01T12:0{number}:00Z", sequence))
            sequence += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["entry", "at", "order"])
        writer.writerows(reversed(entries))


if __name__ == "__main__":
    target = Path("data/private/synthetic-demo.csv")
    if target.exists():
        raise SystemExit("Demo file already exists; it was not overwritten.")
    create_demo(target)
    print(f"Synthetic demonstration only: {target}")
    print("Import using a clearly labeled demo session, never as a real game.")
