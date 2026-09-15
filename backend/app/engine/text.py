"""Russian wording helpers for the engine's explanations."""

from decimal import Decimal

REPS = ("повтор", "повтора", "повторов")
SECONDS = ("секунда", "секунды", "секунд")
SETS = ("подход", "подхода", "подходов")
MINUTES = ("минута", "минуты", "минут")
WORKOUTS = ("тренировка", "тренировки", "тренировок")

PATTERN_NAMES = {
    "squat": "приседание",
    "hinge": "наклон",
    "push_h": "горизонтальный жим",
    "push_v": "вертикальный жим",
    "pull_h": "горизонтальная тяга",
    "pull_v": "вертикальная тяга",
    "lunge": "выпад",
    "carry": "переноска",
    "core": "кор",
    "cardio": "метаболическая работа",
}
HEALTH_NAMES = {
    "knees": "колени",
    "shoulders": "плечи",
    "lower_back": "поясница",
    "wrists": "запястья",
    "neck": "шея",
    "elbows": "локти",
}
GOAL_NAMES = {
    "hypertrophy": "мышечная масса",
    "strength": "сила",
    "endurance": "выносливость",
    "fat_loss": "снижение веса",
    "skill": "навыки",
    "health": "здоровье",
    "maintenance": "поддержание формы",
}
KIND_NAMES = {
    "home": "Дом",
    "outdoor_gym": "Площадка",
    "outdoor_bare": "Улица",
    "travel": "Поездка",
}


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


def duration(seconds: int) -> str:
    """180 → «3 минуты», 90 → «90 секунд»."""
    return count(seconds // 60, MINUTES) if seconds % 60 == 0 else count(seconds, SECONDS)


def listing(items: list[str], last: str = "и") -> str:
    """["a", "b", "c"] → «a, b и c»."""
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} {last} {items[-1]}"
