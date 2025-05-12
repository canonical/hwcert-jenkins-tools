from abc import ABC, abstractmethod
from itertools import repeat
import logging
from time import sleep
from typing import Any, Callable, Optional


logger = logging.getLogger(__name__)


class RetryPolicy(ABC):

    @abstractmethod
    def waits(self):
        raise NotImplementedError


class Linear(RetryPolicy):

    def __init__(
        self,
        times: Optional[int] = None,
        delay: float = 0
    ):
        self.times = times
        self.delay = delay

    def waits(self):
        if self.times:
            yield from repeat(self.delay, self.times)
        else:
            yield from repeat(self.delay)


def retry(script: Callable, policy: Optional[RetryPolicy] = None) -> Any:
    if not policy:
        policy = Linear()
    for wait in policy.waits():
        result = script()
        if result:
            logger.info("%s returned %s", script.__name__, result)
            return result
        logger.info(
            "%s returned %s, retrying%s",
            script.__name__,
            result,
            f" in {wait} seconds" if wait else ""
        )
        sleep(wait)
    result = script()
    if result:
        logger.info("%s returned %s", script.__name__, result)
        return result
    logger.error("Unable to complete '%s'", script.__name__)
    return result
