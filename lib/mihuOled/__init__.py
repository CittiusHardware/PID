"""
Pacote educacional mihuOled.

Uso:
    from mihuOled import oled

    oled.clear()
    oled.text("Ola", 0, 0)
"""

# Guarda a referência real do módulo principal.
from . import mihuOled as _oled_module

# Mantém compatibilidade com importações individuais:
#     from mihuOled import clear, text, circle
from .mihuOled import *

# Definido por último para não ser substituído pela função
# interna chamada oled().
oled = _oled_module
mihuOled = _oled_module

_public_names = [
    name
    for name in dir(_oled_module)
    if not name.startswith("_")
]

if "oled" not in _public_names:
    _public_names.append("oled")

if "mihuOled" not in _public_names:
    _public_names.append("mihuOled")

__all__ = tuple(_public_names)

del _public_names
