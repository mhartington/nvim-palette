"""
Description: Easy toggling ON/OFF of options
License: MIT
"""

import neovim
import msgpack
import logging
import gettext as g
import pandas as pd
import os

logger = logging.getLogger('palette')

locale_dir = "/home/teto/neovim2/build/locale"

@neovim.plugin
class PalettePlugin(object):

    def __init__(self, nvim):
        """
        to ease testing:
        from neovim import attach
        import sys
        # echo serverlist() or v:servername in a running nvim
        nvim = attach('socket', path='/tmp/nvimJHSJGG/0')
        sys.path.append('/home/teto/nvim-palette/rplugin/python3/palette')
        import palette as p

        """
        self.nvim = nvim

        logger.addHandler(NeoVimLoggerHandler(nvim))
        logger.setLevel(logging.DEBUG)

        # filedir = os.path.dirname(os.path.realpath(__file__))
        # filename = os.path.join(filedir, "options.csv"),
        # self.df = pd.read_csv(
        #     os.path.join(filedir, "options.csv"), sep=",",
        #     error_bad_lines=False, warn_bad_lines=True,
        # )
        # pd.read_msgpack just returns a
        # self.handle = unpackb(code_data[1])
        self.df = self.load()

    def load(self):
        r = g.bindtextdomain('nvim', locale_dir)

        fields = ["full_name", "short_desc", "abbreviation", "scope"]
        # for now we embed the mpack fil
        # TODO use $VIMRUNTIME /usr/local/share/nvim/runtime
        fname = '/home/teto/neovim2/build/runtime/data/options.mpack'
        # fname = os.path.join(filedir, "options.mpack"),
        fd = open(fname, 'rb')
        res = msgpack.loads(fd.read())

        df = pd.DataFrame([], columns=fields)
        for entry in res:
            temp = {k.decode(): v.decode() if isinstance(v, bytes) else v for k, v in entry.items()}

        # unpacker = msgpack.Unpacker(fd, use_list=False)
        # for unpacked in unpacker:
        #     print(unpacked)
            df = df.append(temp, ignore_index=True)
        # df = pd.DataFrame(res, columns=fields)
        # df.from_records(res)
        df["scope"] = df["scope"].apply(lambda x: [e.decode() for e in x])
        # print(df)
        return df


    @neovim.function('PaletteGetBools', sync=True)
    def get_bools(self, args):
        """
        fzf accepts a list as input
        """
        entries = []
        df = self.df
        # TODO for now drop columns without desc
        # see options.backup.lua for the version with changes
        # df = df.drop("short_desc")
        # sel = df[df.scope == "global"]
        sel = df
        sel = sel[sel.type == "bool"]
        for row in sel.itertuples():
            if "global" in row.scope:
                try:
                    logger.debug("scope =%r" % row.scope)
                    short_desc = g.gettext(row.short_desc)
                    short_desc += " (switch " + ("OFF" if self.get_option_value(row.full_name, row.scope[0]) else "ON ") + ")"
                    entries.append(short_desc)
                except Exception as e:
                    logger.debug("Option '%s' seems not supported" % row.full_name)

        logger.debug("Sending entries=%r" % entries)
        res = self.nvim.call('PaletteFzf', entries)

    def get_option_value(self, full_name, scope):
        source = None
        if scope == "global":
            source = self.nvim.options
        elif scope == "window":
            source = self.nvim.current.window.options
        elif scope == "buffer":
            source = self.nvim.current.buffer.options
        # TODO else throw error ?
        return source[full_name]

    @neovim.function('PalettePostprocessChoice', sync=True)
    def TranslateToCommand(self, line):
        # BUG in client ? line is a list while vimscript sends it as a string
        line = line[0]
        logger.info("Translating command %s (type %s)" % (line, type(line)))
        stripped = line[:-len(" (switch OFF)")]
        logger.debug("Looking for short_desc=%s" % stripped)
        df = self.df[self.df.short_desc == stripped]
        if len(df) <= 0:
            # TODO escape it replace('"','\\"')
            return ":echom 'Nothing found for \"" + stripped + "\"'"

        row = df.iloc[0, ]
        cmd = "set " + row['full_name'] + "!"
        return cmd


class NeoVimLoggerHandler(logging.Handler):
    def __init__(self, nvim):
        super().__init__()
        self.nvim = nvim

    def emit(self, record):
        msg = self.format(record).replace('"', '`')