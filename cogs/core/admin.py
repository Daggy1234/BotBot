import io

from typing import Union

import discord
from discord.ext import commands
from discord.ext.commands.errors import BadArgument

from jishaku.codeblocks import Codeblock
from jishaku.shell import ShellReader

from bot import BotBase, Context


MAX_FILE_SIZE = 8_000_000


class Admin(commands.Cog):

    def __init__(self, bot: BotBase):
        self.bot = bot
        self._ = None  # for eval env

    async def cog_check(self, ctx: Context):
        return await commands.is_owner().predicate(ctx)

    @commands.command()
    async def load(self, ctx: Context, *, extension: str):
        """Loads an extension.

        `extension`: The name of the extension.
        """
        await ctx.invoke(self.bot.get_command('jsk load'), (extension,))

    @commands.command()
    async def unload(self, ctx: Context, *, extension: str):
        """Unloads an extension.

        `extension`: The name of the extension.
        """
        await ctx.invoke(self.bot.get_command('jsk unload'), (extension,))

    @commands.group(invoke_without_command=None)
    async def reload(self, ctx: Context, *, extension: str):
        """Reloads an extension.

        `extension`: The name of the extension.
        """
        await ctx.invoke(self.bot.get_command('jsk reload'), (extension,))

    @reload.command()
    async def config(self, ctx: Context):
        """Reloads the bot's config."""
        self.config.read('./config.ini')
        await ctx.tick()

    @commands.command()
    async def eval(self, ctx: Context, *, code: Codeblock):
        """Evaluates python code.

        `code`: Python code to run.
        """
        await ctx.invoke(self.bot.get_command('jsk python'), argument=code)

    @commands.command()
    async def sudo(self, ctx: Context, user: Union[discord.Member, discord.User], *, command: str):
        """Runs a command as another user.

        `user`: The user to run the command as.
        `command`: The command to run.
        """
        await ctx.invoke(self.bot.get_command('jsk su'), user, command_string=command)

    @commands.command()
    async def debug(self, ctx: Context, *, command: str):
        """Runs a command with in a debugging context.

        `command`: The command to run.
        """
        await ctx.invoke(self.bot.get_command('jsk debug'), command_string=command)

    @commands.command(aliases=['restart'])
    async def logout(self, ctx: Context):
        """Logs the bot out."""
        await ctx.invoke(self.bot.get_command('jsk shutdown'))

    @commands.command(aliases=['sh'])
    async def shell(self, ctx: Context, *, code: Codeblock):
        """Executes a command in the shell.

        `code`: The command to run in the shell.
        """
        await ctx.invoke(self.bot.get_command('jsk sh'), argument=code)

    @commands.command()
    async def git(self, ctx: Context, *, code: Codeblock):
        """Executes a git commmand.

        `code`: The git command to run.
        """
        await ctx.invoke(self.bot.get_command('jsk git'), argument=code)

    @commands.group()
    async def db(self, ctx: Context):
        ...

    @db.command(name='dump', aliases=['backup'])
    async def db_dump(self, ctx: Context, *, database: str = 'botbot'):
        db_dump = io.StringIO()

        async with ctx.typing():
            with ShellReader(f'pg_dump {database}') as reader:
                async for line in reader:
                    db_dump.write(line)

            file_size = db_dump.tell()
            file_name = f'{database}_backup_{ctx.message.created_at}.sql'

            db_dump.seek(0)
            if file_size > MAX_FILE_SIZE:
                with open(file_name, 'w') as f:
                    f.write(db_dump.getvalue())
                raise BadArgument('DB dump exceeds maximim file size, saved to disk.')

            await ctx.send(file=discord.File(db_dump, file_name))


def setup(bot: BotBase):
    bot.add_cog(Admin(bot))
