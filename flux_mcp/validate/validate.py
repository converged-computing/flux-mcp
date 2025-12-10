import re
from io import StringIO

from flux.cli.batch import BatchCmd
from flux.job.directives import DirectiveParser

import flux_mcp.utils as utils


class Validator(BatchCmd):
    """
    The validator validates a Flux batch script.
    """

    def derive_failure_reason(self, message):
        """
        Why did the directive parsing fail?
        """
        line = None
        if "line" in message:
            line = int(message.split("line", 1)[-1].split(":", 1)[0])

        # E.g., # # Flux
        if "sentinel changed" in message:
            return "sentinel changed", line

        # Directive after top of script
        if "orphan 'flux:'" in message.lower():
            return "orphan flux", line

        if "unknown directive" in message.lower():
            return "unknown directive", line

        # Always investigate edge cases!
        print("Unseen issue with parsing directive, investigate:")
        print(message)
        import IPython

        IPython.embed()

    def get_directive_parser(self, content, changes=None):
        """
        Read batch script into string, and get directive parser

        If failure is due to a line that can be removed, do it.
        """
        if changes is None:
            changes = []
        string_io = StringIO(content)
        try:
            batchscript = DirectiveParser(string_io)
        except Exception as e:
            string_io.close()
            reason, line = self.derive_failure_reason(" ".join(e.args))
            if line is not None:
                lines = content.split("\n")
                deleted_line = lines[line - 1]
                changes.append({"line": deleted_line, "reason": reason})
                del lines[line - 1]
                return self.get_directive_parser("\n".join(lines), changes)

        string_io.close()
        return batchscript, changes

    def unhandled(self, filename):
        return self.parse(filename, return_unhandled=True)

    def validate_file(self, path):
        return self.validate(utils.read_file(path))

    def validate(self, content, fail_fast=True):
        """
        Validate a batch script.
        """
        # Changes are removed lines to get it to read
        batchscript, changes = self.get_directive_parser(content)
        if changes:
            changes = "\n".join(changes)
            raise ValueError(f"Jobspec is invalid, required changes: {changes}")

        # Total number of args so we can calculate how many we got wrong
        errors = []
        if any([re.search("^#FLUX ", x) for x in content.split("\n")]):
            if fail_fast:
                raise ValueError("#FLUX directives need to be FLUX:")
            else:
                errors.append("#FLUX directives need to be FLUX:")

        # SETARGS(['--tasks=5'])
        # SETARGS(['-N', '1'])
        for item in batchscript.directives:
            try:
                if item.action == "SETARGS":
                    self.parser.parse_args(item.args)

            # argparse always SystemExits
            except (Exception, SystemExit) as e:
                name = " ".join(item.args)
                if fail_fast:
                    raise ValueError(f"Invalid batch job directive {name}: {e}")
                else:
                    errors.append(f"{name}: {e}")

        if not fail_fast and errors:
            errors = "\n".join(errors)
            raise ValueError(f"Validation failed at directives:\n{errors}")

    def parse_argument_delta(self, args):
        """
        Get a single parsed arg by looking at the parser delta.
        """
        defaults = self.parser.parse_args([])
        updated = self.parser.parse_args(args)

        # Find what's different - this will only be one value
        for key, value in vars(updated).items():
            if value != getattr(defaults, key):
                yield key, value


def parse_time_to_seconds(time_str):
    """
    Parses a time string like "1h30m", "1d", "50m", "3600s" into seconds.
    """
    if not time_str:
        return None

    total_seconds = 0
    # Regex to find numbers and their units (d, h, m, s)
    pattern = re.compile(r"(\d+)([dhms])")
    matches = pattern.findall(time_str.lower())

    if not matches and time_str.isdigit():
        return int(time_str)

    for value, unit in matches:
        value = int(value)
        if unit == "d":
            total_seconds += value * 86400
        elif unit == "h":
            total_seconds += value * 3600
        elif unit == "m":
            total_seconds += value * 60
        elif unit == "s":
            total_seconds += value

    return total_seconds if total_seconds > 0 else None
