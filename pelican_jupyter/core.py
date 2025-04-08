"""
Core module that handles the conversion from notebook to HTML plus some utilities
"""

import os
import re
from copy import deepcopy

import jinja2
from nbconvert.exporters import HTMLExporter
from pygments.formatters import HtmlFormatter

try:
    # Jupyter
    from traitlets import Integer
except ImportError:
    # IPython < 4.0
    from IPython.utils.traitlets import Integer

try:
    # Jupyter
    from nbconvert.preprocessors import Preprocessor
except ImportError:
    # IPython < 4.0
    from IPython.nbconvert.preprocessors import Preprocessor

try:
    from nbconvert.filters.highlight import _pygments_highlight
except ImportError:
    # IPython < 2.0
    from nbconvert.filters.highlight import _pygment_highlight as _pygments_highlight

try:
    from nbconvert.nbconvertapp import NbConvertApp
except ImportError:
    from IPython.nbconvert.nbconvertapp import NbConvertApp

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


LATEX_CUSTOM_SCRIPT = """
<script type="text/javascript">if (!document.getElementById('mathjaxscript_pelican_#%@#$@#')) {
    var mathjaxscript = document.createElement('script');
    mathjaxscript.id = 'mathjaxscript_pelican_#%@#$@#';
    mathjaxscript.type = 'text/javascript';
    mathjaxscript.src = '//cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.1/MathJax.js?config=TeX-AMS-MML_HTMLorMML';
    mathjaxscript[(window.opera ? "innerHTML" : "text")] =
        "MathJax.Hub.Config({" +
        "    config: ['MMLorHTML.js']," +
        "    TeX: { extensions: ['AMSmath.js','AMSsymbols.js','noErrors.js','noUndefined.js'], equationNumbers: { autoNumber: 'AMS' } }," +
        "    jax: ['input/TeX','input/MathML','output/HTML-CSS']," +
        "    extensions: ['tex2jax.js','mml2jax.js','MathMenu.js','MathZoom.js']," +
        "    displayAlign: 'center'," +
        "    displayIndent: '0em'," +
        "    showMathMenu: true," +
        "    tex2jax: { " +
        "        inlineMath: [ ['$','$'] ], " +
        "        displayMath: [ ['$$','$$'] ]," +
        "        processEscapes: true," +
        "        preview: 'TeX'," +
        "    }, " +
        "    'HTML-CSS': { " +
        " linebreaks: { automatic: true, width: '95% container' }, " +
        "        styles: { '.MathJax_Display, .MathJax .mo, .MathJax .mi, .MathJax .mn': {color: 'black ! important'} }" +
        "    } " +
        "}); ";
    (document.body || document.getElementsByTagName('head')[0]).appendChild(mathjaxscript);
}
</script>
"""


def get_config():
    """Load and return the user's nbconvert configuration.

    Returns:
        The nbconvert configuration object
    """
    app = NbConvertApp()
    app.load_config_file()
    return app.config


def get_html_from_filepath(
    filepath: str,
    start: int = 0,
    end: int = None,
    preprocessors: list = None,
    template: str = None,
    colorscheme: str = None,
) -> tuple:
    """Convert a Jupyter Notebook to HTML.

    Args:
        filepath: Path to the notebook file
        start: First cell index to include
        end: Last cell index to include (exclusive)
        preprocessors: Additional preprocessors to apply
        template: Path to a custom template file
        colorscheme: Pygments color scheme name

    Returns:
        Tuple containing:
            - The HTML content as a string
            - Information dictionary from the exporter
    """
    if preprocessors is None:
        preprocessors = []

    template_file = "base"
    extra_loaders = []
    if template:
        extra_loaders.append(jinja2.FileSystemLoader([os.path.dirname(template)]))
        template_file = os.path.basename(template)

    config = get_config()
    config.update(
        {
            "CSSHTMLHeaderTransformer": {
                "enabled": True,
                "highlight_class": ".highlight-ipynb",
            },
            "SubCell": {"enabled": True, "start": start, "end": end},
        }
    )

    colorscheme = colorscheme or "default"

    config.CSSHTMLHeaderPreprocessor.highlight_class = " .highlight pre "
    config.CSSHTMLHeaderPreprocessor.style = colorscheme
    config.LatexPreprocessor.style = colorscheme
    exporter = HTMLExporter(
        config=config,
        template_file=template_file,
        extra_loaders=extra_loaders,
        filters={"highlight2html": custom_highlighter},
        preprocessors=[SubCell, *preprocessors],
    )
    content, info = exporter.from_filename(filepath)

    return content, info


def parse_css(
    content: str, info: dict, fix_css: bool = True, ignore_css: bool = False
) -> str:
    """Process and combine CSS with notebook HTML content.

    This function handles the CSS styling for the notebook HTML output,
    with options to filter or ignore the Jupyter CSS.

    Args:
        content: The HTML content from the notebook
        info: Information dictionary from the exporter
        fix_css: Whether to filter the Jupyter CSS to remove unnecessary styles
        ignore_css: Whether to completely ignore the Jupyter CSS

    Returns:
        The processed HTML content with appropriate CSS
    """

    def style_tag(styles: str) -> str:
        """Wrap CSS in a style tag."""
        return f'<style type="text/css">{styles}</style>'

    def filter_css(style: str) -> str:
        """Filter Jupyter CSS to keep only notebook-specific styles.

        This is a targeted approach to extract only the Jupyter Notebook CSS
        without extra Bootstrap and webapp styles.
        """
        # Extract only the IPython notebook section
        index = style.find("/*!\n*\n* IPython notebook\n*\n*/")
        if index > 0:
            style = style[index:]

        # Remove the webapp section if present
        index = style.find("/*!\n*\n* IPython notebook webapp\n*\n*/")
        if index > 0:
            style = style[:index]

        # Clean up specific style elements
        style = re.sub(r"color\:\#0+(;)?", "", style)
        style = re.sub(
            r"\.rendered_html[a-z0-9,._ ]*\{[a-z0-9:;%.#\-\s\n]+\}", "", style
        )
        return style_tag(style)

    if ignore_css:
        # Skip all CSS and just add the LaTeX script
        result = content + LATEX_CUSTOM_SCRIPT
    else:
        if fix_css:
            # Apply filtering to each CSS block
            jupyter_css = "\n".join(
                filter_css(style) for style in info["inlining"]["css"]
            )
        else:
            # Include all CSS without filtering
            jupyter_css = "\n".join(
                style_tag(style) for style in info["inlining"]["css"]
            )
        result = jupyter_css + content + LATEX_CUSTOM_SCRIPT

    return result


def custom_highlighter(
    source: str, language: str = "python", metadata: dict = None
) -> str:
    """Apply syntax highlighting with custom CSS classes.

    This function customizes the Pygments syntax highlighting output
    to use a specific CSS class prefix that won't conflict with the theme.

    Args:
        source: The source code to highlight
        language: The programming language for syntax highlighting
        metadata: Additional metadata for the highlighter

    Returns:
        HTML with syntax highlighting applied
    """
    if not language:
        language = "python"

    formatter = HtmlFormatter(cssclass="highlight-ipynb")
    output = _pygments_highlight(source, formatter, language, metadata)
    output = output.replace("<pre>", '<pre class="ipynb">')
    return output


def soup_fix(content: str, add_permalink: bool = False) -> str:
    """Fix issues and enhance HTML content using BeautifulSoup.

    This function applies several improvements to the notebook HTML:
    1. Wraps markdown cells with a div for better styling
    2. Optionally adds permalink anchors to headers
    3. Fixes Jupyter notebook formatting quirks

    Args:
        content: The HTML content from the notebook
        add_permalink: Whether to add permalink anchors to headers

    Returns:
        The processed HTML content

    Note:
        This function requires BeautifulSoup to be installed.
        If BeautifulSoup is not available, the content is returned unmodified.
    """
    if BeautifulSoup is None:
        return content

    soup = BeautifulSoup(content, "html.parser")

    # Add div.cell around markdown cells
    for div in soup.findAll("div", {"class": "text_cell_render"}):
        new_div = soup.new_tag("div")
        new_div["class"] = "cell"
        outer_div = div.find_parent("div")
        outer_div.wrap(new_div)

    # Add permalinks to headers
    if add_permalink:
        for h in soup.findAll(["h1", "h2", "h3", "h4", "h5", "h6"]):
            if not h.get("id"):
                continue

            permalink = soup.new_tag("a", href="#" + h["id"])
            permalink["class"] = ["anchor-link"]
            permalink.string = "#"
            h.append(permalink)

    # Remove explicit MIME type from code cells (language is already in the div class)
    for pre in soup.findAll("pre"):
        if "data-mime-type" in pre.attrs:
            del pre.attrs["data-mime-type"]

    return str(soup)


# ----------------------------------------------------------------------
# Create a preprocessor to slice notebook by cells


class SliceIndex(Integer):
    """An integer trait that accepts None as a valid value.

    Used for notebook cell slicing operations.
    """

    default_value = None

    def validate(self, obj: object, value: int) -> int:
        """Validate the input value, allowing None as a valid option.

        Args:
            obj: The object being validated
            value: The integer value or None

        Returns:
            The validated value
        """
        if value is None:
            return value
        else:
            return super().validate(obj, value)


class SubCell(Preprocessor):
    """A preprocessor to select a slice of the cells of a notebook.

    This preprocessor extracts a subset of cells from a notebook based on
    start and end indices, creating a new notebook with only the selected cells.
    """

    start = SliceIndex(0, config=True, help="First cell index of notebook to include")
    end = SliceIndex(
        None, config=True, help="Last cell index of notebook to include (exclusive)"
    )

    def preprocess(self, nb, resources):
        """Process the notebook by extracting the specified cell slice.

        Args:
            nb: The notebook to process
            resources: Additional resources

        Returns:
            Tuple containing:
                - The processed notebook with only selected cells
                - The resources dictionary
        """
        nbc = deepcopy(nb)
        nbc.cells = nbc.cells[self.start : self.end]
        return nbc, resources
