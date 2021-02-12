import asyncio
import random
import re

from collections import defaultdict
from typing import List, NamedTuple, Type

import discord
from discord.ext import commands, menus
from discord.ext.commands.errors import BadArgument

from bot import BotBase, Context
from utils.tools import ordinal

from .parser import View


ORIGINAL = 4
BIG = 5
SUPER_BIG = 6

NUMBER_EMOJI = (
    '0\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '1\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '2\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '3\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '4\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '5\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '6\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '7\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '8\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '9\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
    '0\ufe0f\N{COMBINING ENCLOSING KEYCAP}',
)

DIE = {
    ORIGINAL: [
        '781923', '442727', '286382', '674674',
        '434257', '612362', '761386', '917136',
        '389292', '912198', '218613', '522074',
        '421587', '319059', '403934', '503529'
    ],
    BIG: [
        '467377', '368015', '881118', '152754', '403491',
        '496754', '322870', '476441', '930914', '124178',
        '985631', '692161', '213957', '930884', '183380',
        '140851', '217378', '853915', '932265', '727123',
        '562516', '215186', '776605', '849463', '410954'
    ],
    SUPER_BIG: [
        '150704', '153141', '695329', '829765', '147583', '433529',
        '154691', '586481', '256164', '470592', '126134', '975732',
        '402085', '235228', '247811', '531376', '440231', '948365',
        '243870', '958379', '432140', '354431', '246147', '518645',
        '413514', '722772', '791934', '553194', '175219', '971067',
        '603808', '294025', '456713', '611644', '173820', '455798'
    ]
}

NUMBER_PATTERN = re.compile('[^0-9]')


class Position(NamedTuple):
    col: int
    row: int


class Board:

    def __init__(self, *, size=ORIGINAL, board=None, magic_number=None):
        self.size = size

        if board is None:
            board = DIE[self.size].copy()
            random.shuffle(board)
            board = [[random.choice(board[row * self.size + column]) for column in range(self.size)] for row in range(self.size)]
        if magic_number is None:
            magic_number = random.randint(00, 99)

        self.columns = board
        self.number = magic_number

    def board_contains(self, word: str, pos: Position = None, passed: List[Position] = []) -> bool:
        # Empty words
        if len(word) == 0:
            return True

        # When starting out
        if pos is None:

            # Check all positions
            for col in range(self.size):
                for row in range(self.size):
                    if self.board_contains(word, Position(col, row)):
                        return True

        # Checking new squares
        elif pos not in passed:
            # Check if letter matches current start of word
            if word[0] == self.columns[pos.col][pos.row]:

                # Check adjacent for next letter
                for x in range(-1, 2):
                    for y in range(-1, 2):

                        # don't check yourself
                        if x == 0 and y == 0:
                            continue

                        new_pos = Position(pos.col + x, pos.row + y)

                        # don't check out of bounds
                        if new_pos.col < 0 or new_pos.col >= self.size or new_pos.row < 0 or new_pos.row >= self.size:
                            continue

                        if self.board_contains(word[1:], new_pos, [*passed, pos]):
                            return True

        # Otherwise cannot find word
        return False

    # @cached_property
    # def legal_words(self) -> Set[str]:
    #     return {word for word in DICTIONARY if self.is_legal(word)}

    def is_legal(self, equation: str) -> bool:

        # strip equals half if needed
        if '=' in equation:
            equation, _ = equation.split('=')

        numbers = re.sub(NUMBER_PATTERN, '', equation)

        if len(numbers) < 3:
            return False
        if not self.board_contains(numbers):
            return False
        return View(equation).parse_full() == self.number

    def points(self, word: str) -> int:
        return 1 if self.is_legal(word) else 0

    def total_points(self, words: List[str]) -> int:
        return sum(self.points(word) for word in words)


class Game(menus.Menu):
    name = 'Foggle'
    footer = None

    def __init__(self, *, size=ORIGINAL, **kwargs):
        self.board = Board(size=size)
        self.setup()
        super().__init__(**kwargs)

    @property
    def state(self):
        state = ''

        for row in range(self.board.size):
            emoji = []
            for column in range(self.board.size):
                number = int(self.board.columns[column][row])
                emoji.append(NUMBER_EMOJI[number])

            state = ' '.join(emoji) + '\n' + state

            state += f'\n\n The magic number is **{self.board.number}**!'

        return discord.Embed(title=self.name, description=state).set_footer(text=self.footer)

    def setup(self):
        raise NotImplementedError

    async def send_initial_message(self, ctx, channel):
        return await channel.send(content='Foggle game started, you have 3 minutes!', embed=self.state)

    async def start(self, *args, **kwargs):
        await super().start(*args, **kwargs)
        # await self.bot.loop.run_in_executor(None, lambda: self.board.legal_words)

    async def finalize(self, timed_out):
        self.bot.dispatch('foggle_game_complete', self.message.channel)

    def get_points(self, words: List[str]) -> int:
        return self.board.total_points(words)

    def check_word(self, word: str) -> bool:
        return self.board.is_legal(word)

    async def check_message(self, message: discord.Message):
        raise NotImplementedError

    @menus.button('\N{BLACK SQUARE FOR STOP}\ufe0f', position=menus.Last(0))
    async def cancel(self, payload):
        await self.message.edit(content='Game Cancelled.')
        self.stop()


class ShuffflingGame(Game):

    def __init__(self, *, size=ORIGINAL, **kwargs):
        super().__init__(size=size, **kwargs)
        self.boards = [self.board]

    def shuffle(self):
        raise NotImplementedError

    async def shuffle_task(self):
        for i in range(5):
            await asyncio.sleep(30)
            if not self._running:
                return

            # Shuffle board
            self.shuffle()
            self.boards.append(self.board)

            # Note Board Updated
            await self.message.channel.send('Board Updated!')

            # Update Board Message
            time = ["2 minutes, 30 seconds", '2 minutes', '1 minute, 30 seconds', '1 minute', '30 seconds'][i]
            await self.message.edit(content=f'Board Updated! You have {time} left!', embed=self.state)

    async def start(self, *args, **kwargs):
        await super().start(*args, **kwargs)
        self.bot.loop.create_task(self.shuffle_task())

    def get_points(self, words: List[str]) -> int:
        points = 0
        for word in words:
            for board in self.boards:
                pts = board.points(word)
                if pts:
                    points += pts
                    break

        return points


class DiscordGame(Game):
    name = 'Discord Foggle'
    footer = 'First to find an equation wins points!'

    @property
    def scores(self):
        embed = discord.Embed()

        i = 0
        old = None

        for user, words in sorted(self.words.items(), key=lambda v: self.get_points(v[1]), reverse=True):
            points = self.get_points(words)

            if points != old:
                old = points
                i += 1

            embed.add_field(name=f'{ordinal(i)}: {user}', value=f'**{len(words)}** words, **{points}** points.', inline=False)

        return embed

    def setup(self):
        self.all_words = set()
        self.words = defaultdict(set)

    async def check_message(self, message: discord.Message):
        word = message.content
        if word is None:
            return

        if not word.isalpha():
            return
        word = word.upper()

        if not self.check_word(word):
            return

        if word in self.all_words:
            return

        # Add to user words
        self.all_words.add(word)
        self.words[message.author].add(word)

        await message.add_reaction('\N{WHITE HEAVY CHECK MARK}')

    async def finalize(self, timed_out: bool):
        await super().finalize(timed_out)
        if timed_out:
            await self.message.edit(content='Game Over!')
            await self.message.reply(embed=self.scores)


class ClassicGame(Game):
    name = 'Classic Foggle'
    footer = 'Keep a list of equations til the end!'

    @property
    def scores(self):
        embed = discord.Embed()

        i = 0
        old = None

        for user, unique in sorted(self.unique_words.items(), key=lambda v: self.board.total_points(v[1]), reverse=True):
            words = self.words[user]
            points = self.board.total_points(unique)

            if points != old:
                old = points
                i += 1

            embed.add_field(name=f'{ordinal(i)}: {user}', value=f'**{len(words)}** words, **{len(unique)}** unique, **{points}** points.', inline=False)

        return embed

    def filter_lists(self):
        for user, word_list in self.word_lists.items():

            for word in word_list.split():
                word = word.strip().upper()

                if not word.isalpha():
                    continue

                if not self.check_word(word):
                    continue

                self.words[user].add(word)

                # Remove from all sets if not unique
                if word in self.used_words:
                    for list in self.unique_words.values():
                        if word in list:
                            list.remove(word)
                    continue

                self.used_words.add(word)
                self.unique_words[user].add(word)

    async def check_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        if not self.over:
            return

        if message.content is None:
            return

        if message.author in self.word_lists:
            return

        self.word_lists[message.author] = message.content
        await message.add_reaction('\N{WHITE HEAVY CHECK MARK}')

    def setup(self):
        self.over = False
        self.used_words = set()
        self.word_lists = dict()
        self.words = defaultdict(set)
        self.unique_words = defaultdict(set)

    async def finalize(self, timed_out: bool):
        await super().finalize(timed_out)

        if timed_out:
            await self.message.edit(content='Game Over!')
            await self.message.reply('Game Over! you have 10 seconds to send in your words.')
            self.over = True
            await asyncio.sleep(10)
            self.filter_lists()
            await self.message.reply(embed=self.scores)


class FlipGame(ShuffflingGame, DiscordGame):
    name = 'Flip Foggle'
    footer = 'Find words as fast as you can, rows will flip positions every 30 seconds.'

    def shuffle(self):
        rows = [[self.board.columns[x][y] for x in range(self.board.size)] for y in range(self.board.size)]
        random.shuffle(rows)
        self.board = Board(size=self.board.size, board=[[rows[x][y] for x in range(self.board.size)] for y in range(self.board.size)])


class FoggleGame(ShuffflingGame, DiscordGame):
    name = 'Foggle Foggle'
    footer = 'Find words as fast as you can, letters will shuffle positions every 30 seconds.'

    def shuffle(self):
        letters = [self.board.columns[y][x] for x in range(self.board.size) for y in range(self.board.size)]
        random.shuffle(letters)
        self.board = Board(size=self.board.size, board=[letters[x * self.board.size:x * self.board.size + self.board.size] for x in range(self.board.size)])


class Foggle(commands.Cog):

    def __init__(self, bot: BotBase):
        self.bot = bot
        self.games = defaultdict(lambda: None)

    def _get_game_type(self, ctx: Context) -> Type[Game]:
        if ctx.invoked_subcommand is None:
            return DiscordGame
        elif ctx.invoked_subcommand is self.foggle_classic:
            return ClassicGame
        elif ctx.invoked_subcommand is self.foggle_flip:
            return FlipGame
        elif ctx.invoked_subcommand is self.foggle_foggle:
            return FoggleGame
        raise BadArgument('Unknown foggle game type')

    def _check_size(self, ctx: Context) -> int:
        if ctx.prefix.upper().endswith('SUPER BIG '):
            return SUPER_BIG
        elif ctx.prefix.upper().endswith('BIG '):
            return BIG
        return ORIGINAL

    @commands.group()
    @commands.max_concurrency(1, per=commands.BucketType.channel)
    async def foggle(self, ctx: Context):
        """Start's a game of Foggle.

        The board size can be set by command prefix.
        `(bb)big foggle` will result in a 5x5 board.
        `(bb)super big foggle` will result in a 6x6 board.

        Players have 3 minutes to find as many equation as they can, the first person to find
        an equation gets the points.
        """
        # Ignore if rules invoke
        if ctx.invoked_subcommand is self.foggle_rules:
            return

        # Determine the game type
        game_type = self._get_game_type(ctx)

        # Start the game
        self.games[ctx.channel] = game = game_type(size=self._check_size(ctx))
        await game.start(ctx, wait=False)

        # Wait for game to end
        def check(channel):
            return channel.id == ctx.channel.id

        channel = await self.bot.wait_for('foggle_game_complete', check=check, timeout=200)
        del self.games[channel]

    @foggle.command(name='classic')
    async def foggle_classic(self, ctx: Context):
        """Starts a cassic game of foggle.

        Players will write down as many words as they can and send after 3 minutes has passed.
        Points are awarded to players with unique equations.
        """
        ...

    @foggle.command(name='flip')
    async def foggle_flip(self, ctx: Context):
        """Starts a flip game of foggle.

        Rows will randomly shuffle every 30s.
        The first person to find an equation gets the points.
        """
        ...

    @foggle.command(name='foggle')
    async def foggle_foggle(self, ctx: Context):
        """Starts a boggling game of foggle.

        All letters will randomly shuffle flip every 30s.
        The first person to finda word gets the points.
        """
        ...

    @foggle.command(name='rules', aliases=['help'])
    async def foggle_rules(self, ctx: Context, type: str = 'discord'):
        """Displays information about a given foggle game type."""
        raise commands.BadArgument('This command has not been implemented yet.')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Check if channel has a game going
        game = self.games[message.channel]
        if game is None:
            return

        await game.check_message(message)


def setup(bot: BotBase):
    bot.add_cog(Foggle(bot))
