"""작은 공용 도구들."""
import functools
import logging
import time

log = logging.getLogger("mirror")


def ttl_cache(seconds: int):
    """인자 없는 함수의 결과를 `seconds`초 동안 캐시한다.

    외부 API 호출이 실패해도, 이전에 받아둔 값이 있으면 그걸 대신 돌려준다.
    (와이파이가 잠깐 끊겨도 미러 화면이 비지 않게 하려는 목적)
    """

    def decorator(fn):
        state = {"ts": 0.0, "val": None}

        @functools.wraps(fn)
        def wrapper():
            if state["val"] is not None and time.time() - state["ts"] < seconds:
                return state["val"]
            try:
                state["val"] = fn()
                state["ts"] = time.time()
            except Exception as e:  # noqa: BLE001
                if state["val"] is None:
                    raise
                log.warning("%s 갱신 실패, 이전 값 사용: %s", fn.__name__, e)
            return state["val"]

        return wrapper

    return decorator


def safe(fn, default=None):
    """fn() 실행 중 에러가 나도 서버가 죽지 않게 default를 돌려준다."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        log.warning("%s 실패: %s", getattr(fn, "__name__", "call"), e)
        return default
