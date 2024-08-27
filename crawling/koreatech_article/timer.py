from time import time


def timer(func):
    def wrapper():
        start = time()
        func()
        end = time()
        print(f"--- {(end - start) * 10 ** 3:.3f} ms ---")

    return wrapper
