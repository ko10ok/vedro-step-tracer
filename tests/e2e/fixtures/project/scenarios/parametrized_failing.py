import vedro
from vedro import params


class Scenario(vedro.Scenario):
    """
    Параметризованный падающий сценарий без трассируемых вызовов — нужен
    только для проверки, что в полном дампе дерева (``print_to_stdout``)
    отдельные запуски одного шаблона визуально разделены (фидбек Влады №2:
    "для параметризованных сценариев в мейлере хотелось бы более явного
    разделения между отдельными запусками").
    """

    subject = "trace a parametrized failing call ({user_id})"

    @params(1)
    @params(2)
    def __init__(self, user_id):
        self.user_id = user_id

    def given_nothing(self):
        pass

    def then_it_should_fail_on_purpose(self):
        assert self.user_id == 999
