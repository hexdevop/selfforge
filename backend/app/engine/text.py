"""Russian wording helpers for the engine's explanations."""

from decimal import Decimal

REPS = ("повтор", "повтора", "повторов")
SECONDS = ("секунда", "секунды", "секунд")
SETS = ("подход", "подхода", "подходов")
WORKOUTS = ("тренировка", "тренировки", "тренировок")
DAYS = ("день", "дня", "дней")


def plural(n: int, forms: tuple[str, str, str]) -> str:
    """plural(5, REPS) → «повторов»."""
    n = abs(n) % 100
    if 11 <= n <= 14:
        return forms[2]
    if n % 10 == 1:
        return forms[0]
    if 2 <= n % 10 <= 4:
        return forms[1]
    return forms[2]


def count(n: int, forms: tuple[str, str, str]) -> str:
    return f"{n} {plural(n, forms)}"


def kg(weight: Decimal) -> str:
    """Decimal("17.50") → «17,5 кг»."""
    return f"{weight.normalize():f}".replace(".", ",") + " кг"
