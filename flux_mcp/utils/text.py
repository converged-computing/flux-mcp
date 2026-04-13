import re
import shlex


def format_rules(rules):
    return "\n".join([f"- {r}" for r in rules])


def ensure_command(command):
    if isinstance(command, str):
        command = shlex.split(command)
    return command


def ensure_bool(value):
    """
    Overly verbose function to ensure numerical
    """
    if value is None:
        return value
    if value in ["True", "true", "yes", "t", "T", "y", 1, "1", True]:
        return True
    if value in ["False", "false", "no", "f", "F", "n", 0, "0", False]:
        return False


def ensure_int(number):
    """
    Overly verbose function to ensure numerical
    """
    if number is None:
        return number
    try:
        return int(number)
    except:
        return number


def get_code_block(content, code_type):
    """
    Parse a code block from the response
    """
    pattern = f"```(?:{code_type})?\n(.*?)```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    if content.startswith(f"```{code_type}"):
        content = content[len(f"```{code_type}") :]
    if content.startswith("```"):
        content = content[len("```") :]
    if content.endswith("```"):
        content = content[: -len("```")]
    return content.strip()
