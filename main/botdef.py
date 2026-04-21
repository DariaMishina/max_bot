import aiomax
from aiomax import utils as _aiomax_utils
from main.config_reader import config

bot = aiomax.Bot(
    config.effective_bot_token.get_secret_value(),
    default_format='html'
)


# MAX API задеприкетил query-параметр ?access_token=... и теперь отбивает запросы
# с ошибкой "deprecated.token". Библиотека aiomax по-прежнему шлёт токен в query.
# Пропатчиваем базовые HTTP-методы Bot, чтобы токен уезжал в заголовке Authorization.
# Починит все сценарии разом: polling, send_message-рассылки, вызовы из webhook'а.
def _make_authed_method(http_method: str):
    async def _method(self, *args, **kwargs):
        if self.session is None:
            raise Exception("Session is not initialized")

        params = kwargs.pop("params", {}) or {}
        params.pop("access_token", None)

        headers = kwargs.pop("headers", {}) or {}
        headers.setdefault("Authorization", self.access_token)

        session_method = getattr(self.session, http_method)
        response = await session_method(
            *args, params=params, headers=headers, **kwargs
        )

        exception = await _aiomax_utils.get_exception(response)
        if exception:
            raise exception
        return response

    _method.__name__ = http_method
    return _method


for _m in ("get", "post", "patch", "put", "delete"):
    setattr(aiomax.Bot, _m, _make_authed_method(_m))
