from sincronizar_operadores import sincronizar_operadores


def main():
    nuevos, actualizados, eliminados, conflictos = sincronizar_operadores()
    print(
        f"Sincronización completada. Nuevos: {nuevos}. "
        f"Nombres actualizados: {actualizados}. Eliminados: {eliminados}."
    )
    if conflictos:
        print(f"Códigos omitidos por tener nombres distintos en la fuente: {conflictos}.")


if __name__ == "__main__":
    main()
