import vedro

from unit.contexts.step_runner import run_step_async
from unit.contexts.traced_calls import async_leaf
from vedro_step_tracer.tracing.nodes import StepNode

_DELAY = 0.05


class Scenario(vedro.Scenario):
    subject = "tree: an async call's duration includes the time spent awaiting"

    async def when_a_step_awaits_a_coroutine_that_sleeps(self):
        async def when(self):
            await async_leaf(_DELAY)

        self.call_tree = await run_step_async(when)

    def then_the_coroutine_call_should_be_a_single_node(self):
        calls = [n for n in self.call_tree if isinstance(n, StepNode)]
        assert len(calls) == 1
        self.node = calls[0]

    def and_its_duration_should_cover_the_await_period(self):
        assert self.node.duration is not None
        assert self.node.duration >= _DELAY * 0.8
