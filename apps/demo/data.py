"""Sample data for demo accounts: a believable month of spending for someone living in Spain.

The texts are user-facing, so they are in Spanish like the rest of the demo.
"""

from decimal import Decimal

CATEGORIES = [
    "Vivienda",
    "Supermercado",
    "Restaurantes",
    "Transporte",
    "Ocio",
    "Suscripciones",
    "Salud",
    "Ropa",
]

# Monthly budgets for some categories, so the demo shows the budgets card. A couple of them
# usually end up close to or over the limit, which is the interesting case.
BUDGETS = {
    "Supermercado": Decimal("350.00"),
    "Restaurantes": Decimal("150.00"),
    "Ocio": Decimal("100.00"),
    "Ropa": Decimal("80.00"),
}

# Expenses that happen once a month: (category, description, day of the month, min, max).
MONTHLY = [
    ("Vivienda", "Alquiler", 1, Decimal("650.00"), Decimal("650.00")),
    ("Vivienda", "Luz", 8, Decimal("38.00"), Decimal("72.00")),
    ("Vivienda", "Internet y móvil", 5, Decimal("39.90"), Decimal("39.90")),
    ("Transporte", "Abono de transporte", 1, Decimal("20.00"), Decimal("20.00")),
    ("Suscripciones", "Gimnasio", 2, Decimal("34.90"), Decimal("34.90")),
    ("Suscripciones", "Netflix", 12, Decimal("13.99"), Decimal("13.99")),
    ("Suscripciones", "Spotify", 15, Decimal("11.99"), Decimal("11.99")),
]

# Expenses that happen a few times a month on random days:
# (category, possible descriptions, min times, max times, min amount, max amount).
OCCASIONAL = [
    (
        "Supermercado",
        ["Mercadona", "Lidl", "Carrefour", "Frutería del barrio", "Panadería"],
        6,
        9,
        Decimal("8.00"),
        Decimal("85.00"),
    ),
    (
        "Restaurantes",
        ["Menú del día", "Cena con amigos", "Café y tostada", "Pizza a domicilio", "Tapas"],
        3,
        7,
        Decimal("6.00"),
        Decimal("48.00"),
    ),
    (
        "Transporte",
        ["Gasolina", "Taxi", "Tren de cercanías", "Parking"],
        1,
        3,
        Decimal("5.00"),
        Decimal("55.00"),
    ),
    (
        "Ocio",
        ["Cine", "Concierto", "Libro", "Escape room", "Bolera"],
        1,
        4,
        Decimal("8.00"),
        Decimal("45.00"),
    ),
    ("Salud", ["Farmacia", "Fisioterapia"], 0, 2, Decimal("6.00"), Decimal("45.00")),
    (
        "Ropa",
        ["Zapatillas", "Camiseta", "Pantalón", "Chaqueta"],
        0,
        2,
        Decimal("15.00"),
        Decimal("90.00"),
    ),
]
