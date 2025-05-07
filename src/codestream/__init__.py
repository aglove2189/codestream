import argparse
import fnmatch
import itertools
import os
import random
import re
import time

from pygments import lexers
from pygments.styles import get_style_by_name
from pygments.token import Token
from pygments.util import ClassNotFound
from rich.console import Console
from rich.style import Style

console = Console()


def parse_gitignore(gitignore_path):
    """Parse .gitignore and return a list of patterns."""
    patterns = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
    return patterns


def is_ignored(path, patterns, root_dir):
    """Check if a path matches any .gitignore pattern."""
    rel_path = os.path.relpath(path, root_dir)
    for pattern in patterns:
        # Support directory ignore (trailing slash)
        if pattern.endswith("/") and rel_path.startswith(pattern.rstrip("/")):
            return True
        # Support glob patterns
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        # Support negation (!pattern)
        if pattern.startswith("!") and fnmatch.fnmatch(rel_path, pattern[1:]):
            return False
    return False


def find_code_files(root_dir):
    """Recursively finds code files in a directory, skipping .gitignore patterns."""
    gitignore_path = os.path.join(root_dir, ".gitignore")
    patterns = parse_gitignore(gitignore_path)
    console.print(f"Scanning [cyan]{os.path.abspath(root_dir)}[/cyan]")

    code_files = []
    for subdir, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            file_path = os.path.join(subdir, f)
            if is_ignored(file_path, patterns, root_dir):
                continue
            # Try to guess if it's a code file
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read(4096)
                lexers.guess_lexer_for_filename(file_path, content)
                code_files.append(file_path)
            except (ClassNotFound, UnicodeDecodeError, IsADirectoryError):
                continue
            except Exception as e:
                console.print(f"[yellow]Skipping {file_path}: {e}[/yellow]")

    return code_files


def tokenize_code_basic(text: str):
    """Basic tokenizer using regex (fallback)."""
    token_pattern = re.compile(r"(\w+|\s+|.)")
    tokens = token_pattern.findall(text)
    return [(Token.Text, token) for token in tokens if token]  # Wrap in Pygments-like tuple


def build_style_map(theme_name: str) -> tuple[dict, Style]:
    # Get the style definitions from the chosen Pygments theme
    style_map = {}
    try:
        pygments_style = get_style_by_name(theme_name)
    except ClassNotFound:
        return style_map, None

    # Create a mapping from Pygments Token types to Rich Styles
    # This is a simplified mapping; a full mapping is more complex
    for token_type, style_dict in pygments_style:
        # Construct Rich style: bold, italic, underline, color
        rich_style_str = ""
        if style_dict["bold"]:
            rich_style_str += "bold "
        if style_dict["italic"]:
            rich_style_str += "italic "
        if style_dict["underline"]:
            rich_style_str += "underline "
        if style_dict["color"]:
            rich_style_str += f"#{style_dict['color']} "  # Use hex color

        style_map[token_type] = Style.parse(rich_style_str.strip())

    return style_map, pygments_style


def display_stream(file_path, tokens_per_second=5, theme_name="lightbulb"):
    """Reads and displays a file token by token with syntax highlighting."""
    console.print(f"\n--- [bold cyan]{file_path}[/bold cyan] ---\n")
    time.sleep(0.5)

    with open(file_path, encoding="utf-8", errors="ignore") as f:
        content = f.read()

    try:
        # Guess the lexer based on filename and content analysis
        lexer = lexers.guess_lexer_for_filename(file_path, content)
        tokens = lexer.get_tokens(content)
    except Exception:
        console.print("[yellow]No specific lexer found, using plain text.[/yellow]")
        # Use a basic lexer or our fallback tokenizer
        tokens = tokenize_code_basic(content)

    style_map, pygments_style = build_style_map(theme_name)

    for ttype, value in tokens:
        # Determine the style for this token type
        style = Style()  # Default empty style
        if pygments_style:
            current_type = ttype
            while current_type != Token:  # Go up the hierarchy e.g. Name.Function -> Name -> Token
                if current_type in style_map:
                    style = style_map[current_type]
                    break
                if current_type.parent is None:
                    break  # Safety break
                current_type = current_type.parent

        console.print(value, style=style, end="")
        time.sleep(tokens_per_second / 60)


def run(dir, tokens_per_second, theme_name):
    """Main loop to find files and start streaming."""
    code_files = find_code_files(dir)
    random.shuffle(code_files)

    console.print(f"Found [bold green]{len(code_files):,}[/bold green] files.")

    for code_file in itertools.cycle(code_files):
        display_stream(code_file, tokens_per_second=tokens_per_second, theme_name=theme_name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", type=str, default=".", help="Directory of source code")
    parser.add_argument("-t", "--tokens", type=int, default=5, help="Tokens per second")
    parser.add_argument("--theme", type=str, default="lightbulb", help="pygments theme name")
    args, _ = parser.parse_known_args()

    try:
        run(args.dir, args.tokens, args.theme)
    except KeyboardInterrupt:
        return



if __name__ == "__main__":
    main()
