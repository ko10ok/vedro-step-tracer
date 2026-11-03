"""Конфиг vedro для прогона тестов самого плагина (unit + e2e)."""

import vedro


class Config(vedro.Config):

    class Registry(vedro.Config.Registry):
        pass
