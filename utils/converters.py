from functools import partial

from discord.ext import commands

import ampharos
from ampharos.types import Pokemon

from bot import Context
from .objects import Code

from dateparser.search import search_dates
from typing import Any


class CodeConverter(commands.Converter):
    async def convert(self, ctx: Context, argument: str):
        if argument.startswith('```') and argument.endswith('```'):
            return Code('\n'.join(argument.split('\n')[1:-1]))
        return Code(argument)


_DATEPARSER_SETTINGS = {
    'PREFER_DATES_FROM': 'future',
    'PREFER_DAY_OF_MONTH': 'first',
    'RETURN_AS_TIMEZONE_AWARE': False,
    'PARSERS': ['relative-time', 'absolute-time', 'timestamp', 'base-formats']
}


class WhenAndWhat(commands.Converter):
    async def convert(self, ctx: Context, argument: str):
        find_dates = partial(search_dates, argument, languages=['en'], settings=_DATEPARSER_SETTINGS)
        dates = await ctx.bot.loop.run_in_executor(None, find_dates)

        if not dates:
            raise commands.BadArgument('Could not determine date...')
        if len(dates) > 1:
            raise commands.BadArgument('Too many dates specified...')
        text, when = dates[0]

        index = argument.find(text)
        before = argument[:index]
        after = argument[index + len(text):]

        if len(before) > len(after):
            what = before
        else:
            what = after

        return when, what.strip()


class _BasePokemonConverter(commands.Converter):
    _error_message = 'Could not determine pokemon object type. {}'

    @classmethod
    def _type(cls, x):
        return None

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str) -> Any:
        result = await cls._type(argument)
        if result is None:
            raise commands.BadArgument(cls._error_message.format(argument))
        return result


class PokemonConverter(_BasePokemonConverter):
    """Converts to :class:`bot.utils.pokemon.core.Pokemon`"""
    _error_message = 'Could not find pokemon with name {}.'

    @classmethod
    def _type(cls, x):
        return ampharos.pokemon(x)


__converters__ = {
    Code: CodeConverter,
    # Tuple[datetime.datetime, str]: WhenAndWhat
    Pokemon: PokemonConverter
}
