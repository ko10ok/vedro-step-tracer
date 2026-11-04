import asyncio

import vedro

from vedro_step_tracer.exclude import DEFAULT_EXCLUDED_VALUE_TYPES, ValueExcludeRules


class Scenario(vedro.Scenario):
    """
    Регрессия на реальный баг: функция открывает subprocess с pipe-потоками
    (как ``CliRunner.run_vedro`` в примере из issue) — без исключения
    ``safe_copy`` либо падает на глубоком копировании, либо отдаёт живую
    ссылку на ``Process``/его транспорт, что ломает финализацию при выходе
    из интерпретатора (``Exception ignored in: ... __del__ ...``).
    Проверяем, что дефолтные правила ловят и сам Process, и его внутренний
    транспорт (приватный платформенный подкласс вроде
    ``_UnixSubprocessTransport``) через публичные ABC, без перечисления
    приватных имён классов.
    """

    subject = "exclude: default rules catch a real asyncio subprocess's Process and transport"

    async def given_a_real_subprocess_with_pipes(self):
        self.process = await asyncio.create_subprocess_exec(
            "true",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await self.process.wait()

    def when_checking_the_process_and_its_transport_against_the_default_rules(self):
        self.rules = ValueExcludeRules(DEFAULT_EXCLUDED_VALUE_TYPES)

    def then_the_process_object_itself_should_be_excluded(self):
        assert self.rules.excluded(self.process) is True

    def and_its_transport_should_be_excluded_too(self):
        transport = self.process._transport
        assert self.rules.excluded(transport) is True
