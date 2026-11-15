import vedro

from unit.contexts.step_runner import run_step_async
from unit.contexts.traced_calls import async_twice
from vedro_step_tracer.tracing.nodes import StepNode

_DELAY = 0.05


class Scenario(vedro.Scenario):
    subject = "tree: two awaits of the same coroutine stay two separate calls"

    async def when_a_coroutine_awaits_the_same_function_twice(self):
        async def when(self):
            await async_twice(_DELAY)

        self.call_tree = await run_step_async(when)

    def then_the_outer_coroutine_should_contain_two_inner_calls(self):
        outer = [n for n in self.call_tree if isinstance(n, StepNode)][0]
        self.inner_calls = [n for n in outer.children if isinstance(n, StepNode)]
        assert len(self.inner_calls) == 2

    def and_each_inner_call_duration_should_cover_its_own_await(self):
        for call in self.inner_calls:
            assert call.duration is not None
            assert call.duration >= _DELAY * 0.8
