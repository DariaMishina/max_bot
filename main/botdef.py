import aiomax
from main.config_reader import config

bot = aiomax.Bot(
    config.effective_bot_token.get_secret_value(),
    default_format='html'
)
