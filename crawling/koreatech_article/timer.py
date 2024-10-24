from time import time
from functools import wraps
from contextlib import contextmanager


@contextmanager
def _timer_core():
    start = time()
    try:
        yield
    except Exception as e:
        raise e
    finally:
        end = time()
        print(f"--- {(end - start) * 10 ** 3:.3f} ms ---")


def _timer_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with _timer_core():
            return func(*args, **kwargs)

    return wrapper


def timer(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        # 데코레이터로 사용된 경우
        return _timer_decorator(args[0])
    elif len(args) == 0 and len(kwargs) == 0:
        # 컨텍스트 매니저로 사용된 경우
        return _timer_core()
    else:
        raise ValueError("Invalid use of timer")
