import ast
import json
import os
import re
import tempfile
from shutil import copyfile
from typing import Any, ClassVar

from pelican import signals
from pelican.readers import BaseReader, HTMLReader, MarkdownReader

from .core import get_html_from_filepath, parse_css

try:
    # Py3k
    from html.parser import HTMLParser
except ImportError:
    # Py2.7
    from HTMLParser import HTMLParser


def register() -> None:
    """Register the new 'ipynb' reader with Pelican.

    This function connects to Pelican's initialization signal and adds
    the IPythonNB reader to handle .ipynb files.
    """

    def add_reader(arg: Any) -> None:
        arg.settings["READERS"]["ipynb"] = IPythonNB

    signals.initialized.connect(add_reader)


class IPythonNB(BaseReader):
    """Extends the Pelican BaseReader to handle .ipynb files as a markup language.

    Setup in pelicanconf.py:
    ```
    MARKUP = ('md', 'ipynb')
    ```
    """

    enabled = True
    file_extensions: ClassVar[list[str]] = ["ipynb"]

    def read(self, filepath: str) -> tuple[str, dict[str, Any]]:
        """Read and parse an IPython notebook file.

        Args:
            filepath: Path to the .ipynb file

        Returns:
            Tuple containing the HTML content and parsed metadata

        Raises:
            Exception: If metadata cannot be found
        """
        metadata: dict[str, Any] = {}
        metadata["jupyter_notebook"] = True
        start = 0
        end = None

        # Files
        filedir = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        metadata_filename = os.path.splitext(filename)[0] + ".nbdata"
        metadata_filepath = os.path.join(filedir, metadata_filename)

        if os.path.exists(metadata_filepath):
            # Found .nbdata file - process it using Pelican MD Reader
            md_reader = MarkdownReader(self.settings)
            _content, metadata = md_reader.read(metadata_filepath)
        elif self.settings.get("IPYNB_MARKUP_USE_FIRST_CELL"):
            # No external .md file: Load metadata from the first cell of the notebook
            with open(filepath) as ipynb_file:
                nb_json = json.load(ipynb_file)

            metacell = "\n".join(nb_json["cells"][0]["source"])
            # Convert Markdown title and listings to standard metadata items
            metacell = re.sub(r"^#+\s+", "title: ", metacell, flags=re.MULTILINE)
            metacell = re.sub(r"^\s*[*+-]\s+", "", metacell, flags=re.MULTILINE)

            # Create temporary file for markdown reader
            # We close and delete the file after reading to avoid file lock issues on systems like Windows
            with tempfile.NamedTemporaryFile(
                "w+", encoding="utf-8", delete=False
            ) as metadata_file:
                md_reader = MarkdownReader(self.settings)
                metadata_file.write(metacell)
                metadata_file.flush()
                metadata_file.close()
                _content, metadata = md_reader.read(metadata_file.name)
                os.remove(metadata_file.name)
                # Skip metacell
                start = 1
        else:
            raise Exception(
                f"Error processing {filepath}: "
                "Could not find metadata in: .nbdata file or in the first cell of the notebook. "
                "If this notebook is used with liquid tags then you can safely ignore this error."
            )

        if "subcells" in metadata:
            start, end = ast.literal_eval(metadata["subcells"])

        # Process notebook
        preprocessors = self.settings.get("IPYNB_PREPROCESSORS", [])
        template = self.settings.get("IPYNB_EXPORT_TEMPLATE", None)
        content, info = get_html_from_filepath(
            filepath,
            start=start,
            end=end,
            preprocessors=preprocessors,
            template=template,
            colorscheme=self.settings.get("IPYNB_COLORSCHEME"),
        )

        # Generate summary: Do it before cleaning CSS
        self._generate_summary(content, metadata, filename)

        # Process content
        content = self._process_content(content, info, filepath, metadata)

        return content, metadata

    def _generate_summary(
        self, content: str, metadata: dict[str, Any], filename: str
    ) -> None:
        """Generate a summary if one doesn't exist in metadata.

        Args:
            content: HTML content
            metadata: Article metadata dict to update
            filename: Name of the notebook file
        """
        keys = [k.lower() for k in metadata]
        use_meta_summary = self.settings.get("IPYNB_GENERATE_SUMMARY", True)

        if "summary" not in keys and use_meta_summary:
            parser = MyHTMLParser(self.settings, filename)
            content_with_body = f"<body>{content}</body>"
            parser.feed(content_with_body)
            parser.close()
            metadata["summary"] = parser.summary

    def _process_content(
        self,
        content: str,
        info: dict[str, Any],
        filepath: str,
        metadata: dict[str, Any],
    ) -> str:
        """Process and fix content, save notebook if needed.

        Args:
            content: HTML content to process
            info: Information dict from notebook processing
            filepath: Path to original notebook
            metadata: Article metadata

        Returns:
            Processed HTML content
        """
        # Fix CSS
        fix_css = self.settings.get("IPYNB_FIX_CSS", True)
        ignore_css = self.settings.get("IPYNB_SKIP_CSS", False)
        content = parse_css(content, info, fix_css=fix_css, ignore_css=ignore_css)

        # Save notebook copy if configured
        if self.settings.get("IPYNB_NB_SAVE_AS"):
            self._save_notebook_copy(filepath, metadata)

        return content

    def _save_notebook_copy(self, filepath: str, metadata: dict[str, Any]) -> None:
        """Save a copy of the notebook to the output directory.

        Args:
            filepath: Path to the original notebook
            metadata: Article metadata to update with notebook path
        """
        output_path = self.settings.get("OUTPUT_PATH")
        nb_output_fullpath = self.settings.get("IPYNB_NB_SAVE_AS").format(**metadata)
        nb_output_dir = os.path.join(output_path, os.path.dirname(nb_output_fullpath))

        if not os.path.isdir(nb_output_dir):
            os.makedirs(nb_output_dir, exist_ok=True)

        copyfile(filepath, os.path.join(output_path, nb_output_fullpath))
        metadata["nb_path"] = nb_output_fullpath


class MyHTMLParser(HTMLReader._HTMLParser):
    """Custom Pelican HTML parser to create the content summary.

    Summary generation stops if it finds any div containing ipython notebook code cells.
    This ensures valid HTML for the summary, rather than using simple string splits
    which could break the HTML structure and cause errors in the theme.

    Note: The summary length may not be exactly as specified since it stops at
    completed div/p/li/etc tags.
    """

    def __init__(self, settings: dict[str, Any], filename: str):
        """Initialize the HTML parser.

        Args:
            settings: Pelican settings dictionary
            filename: Name of the file being processed
        """
        HTMLReader._HTMLParser.__init__(self, settings, filename)
        self.settings = settings
        self.filename = filename
        self.wordcount = 0
        self.summary: str | None = None

        self.stop_tags = self.settings.get(
            "IPYNB_STOP_SUMMARY_TAGS",
            [
                ("div", ("class", "input")),
                ("div", ("class", "output")),
                ("h2", ("id", "Header-2")),
            ],
        )
        if "IPYNB_EXTEND_STOP_SUMMARY_TAGS" in self.settings:
            self.stop_tags.extend(self.settings["IPYNB_EXTEND_STOP_SUMMARY_TAGS"])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Process start tags in the HTML.

        Args:
            tag: HTML tag name
            attrs: List of attribute tuples
        """
        HTMLReader._HTMLParser.handle_starttag(self, tag, attrs)

        if self.wordcount < self.settings["SUMMARY_MAX_LENGTH"]:
            mask = [
                stoptag[0] == tag and (stoptag[1] is None or stoptag[1] in attrs)
                for stoptag in self.stop_tags
            ]
            if any(mask):
                self.summary = self._data_buffer
                self.wordcount = self.settings["SUMMARY_MAX_LENGTH"]

    def handle_endtag(self, tag: str) -> None:
        """Process end tags in the HTML.

        Args:
            tag: HTML tag name
        """
        HTMLReader._HTMLParser.handle_endtag(self, tag)

        if self.wordcount < self.settings["SUMMARY_MAX_LENGTH"]:
            self.wordcount = len(strip_tags(self._data_buffer).split(" "))
            if self.wordcount >= self.settings["SUMMARY_MAX_LENGTH"]:
                self.summary = self._data_buffer


def strip_tags(html: str) -> str:
    """Strip HTML tags from HTML content.

    This function is useful for summary creation when counting words.

    Args:
        html: HTML content to strip tags from

    Returns:
        Plain text content with HTML tags removed
    """
    s = HTMLTagStripper()
    s.feed(html)
    return s.get_data()


class HTMLTagStripper(HTMLParser):
    """Custom HTML Parser to strip HTML tags.

    This class is useful for summary creation when only the text content is needed.
    """

    def __init__(self) -> None:
        """Initialize the HTML tag stripper."""
        HTMLParser.__init__(self)
        self.reset()
        self.fed: list[str] = []

    def handle_data(self, html: str) -> None:
        """Process data between HTML tags.

        Args:
            html: Text content found between tags
        """
        self.fed.append(html)

    def get_data(self) -> str:
        """Get the accumulated data.

        Returns:
            Joined text content with HTML tags removed
        """
        return "".join(self.fed)
