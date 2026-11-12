"""Validacion comun de pesos enteros, sin conversiones silenciosas."""
import re

MAXIMO_BIGINT_SQL = 9_223_372_036_854_775_807
# Los formularios y respuestas JSON usan Number en JavaScript: mantener exactitud.
MAXIMO_MONTO_APLICACION = 9_007_199_254_740_991
PESOS_ENTEROS = re.compile(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]{1,3}(?:,[0-9]{3})+)\Z")


def leer_valor_monetario(valor, nombre, *, obligatorio=False):
    """Acepta cero, digitos y grupos de miles; rechaza negativos y decimales.

    Campos opcionales vacios se guardan como NULL. La obligatoriedad corresponde
    a la columna de destino. El resultado siempre es int o None.
    """
    if valor is not None and (isinstance(valor, bool) or not isinstance(valor, (str, int))):
        raise ValueError(f"{nombre} debe ser un número entero en pesos, sin decimales.")
    texto = str(valor).strip() if valor is not None else ""
    if not texto:
        if obligatorio:
            raise ValueError(f"{nombre} es obligatorio.")
        return None
    if texto.startswith("$"):
        texto = texto[1:].strip()
    if not PESOS_ENTEROS.fullmatch(texto):
        raise ValueError(f"{nombre} debe ser un número entero en pesos, sin decimales.")
    digitos = texto.replace(".", "").replace(",", "").lstrip("0") or "0"
    # Limitar longitud antes de int() evita conversiones desmesuradas.
    limite = str(min(MAXIMO_BIGINT_SQL, MAXIMO_MONTO_APLICACION))
    if len(digitos) > len(limite) or (len(digitos) == len(limite) and digitos > limite):
        raise ValueError(f"{nombre} supera el valor máximo permitido ({limite} pesos).")
    return int(digitos)
