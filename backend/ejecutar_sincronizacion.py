import time
from sincronizar_operadores import sincronizar_operadores


def main():
    inicio = time.time()

    try:
        sincronizar_operadores()
        
    except Exception as e:
        raise


if __name__ == "__main__":
    main()