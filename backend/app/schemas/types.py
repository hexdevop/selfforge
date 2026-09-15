from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer

# Weights travel as strings with two decimals ("17.50") so no float rounding sneaks in
# (docs/04-api.md). Always kilograms.
WeightKg = Annotated[Decimal, PlainSerializer(lambda kg: f"{kg:.2f}", return_type=str)]
PositiveKg = Annotated[WeightKg, Field(gt=0, le=500, decimal_places=2)]
