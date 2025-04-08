# Pelican-Jupyter Plugin: Developer Documentation

## Overview

The `pelican-jupyter` plugin enables Pelican (a static site generator) to process Jupyter notebooks (`.ipynb` files) as content sources. This document provides an in-depth technical explanation of how the plugin works, its architecture, and key components for developers interested in maintaining or extending the plugin.

## Architecture

The plugin is organized into three main components:

1. **Core module (`core.py`)**: Contains the underlying functionality for converting Jupyter notebooks to HTML.
2. **Markup module (`markup.py`)**: Implements notebook handling as a native content type in Pelican.
3. **Liquid module (`liquid.py`)**: Provides a liquid tag interface to embed notebooks in Markdown content.

```
pelican_jupyter/
├── __init__.py          # Package initialization and version management
├── core.py              # Core conversion functionality 
├── liquid.py            # Liquid tag implementation
├── markup.py            # Markup implementation (treating .ipynb as content)
├── tests/               # Test suite
└── vendor/              # Bundled dependencies (liquid_tags)
```

## Component Breakdown

### Core Module (`core.py`)

The core module handles the actual conversion of Jupyter notebooks to HTML content suitable for Pelican. Key functions include:

1. **`get_html_from_filepath()`**: Converts a notebook file to HTML content with appropriate styling.
2. **`parse_css()`**: Processes and cleans the CSS to avoid conflicts with Pelican themes.
3. **`custom_highlighter()`**: Provides syntax highlighting for code cells with custom CSS class prefixing.
4. **`SubCell` class**: A preprocessor that extracts a subset of cells from a notebook.

The module handles compatibility with different versions of Jupyter/IPython through multiple try/except import blocks, allowing the plugin to work with various Jupyter versions.

The core module also contains a custom MathJax configuration script (`LATEX_CUSTOM_SCRIPT`) that properly renders LaTeX content in the generated HTML.

### Markup Module (`markup.py`)

This module implements a custom Pelican reader (`IPythonNB`) that enables Pelican to process `.ipynb` files directly as a content type. Key components:

1. **`register()`**: Connects the custom reader to Pelican's initialization signal.
2. **`IPythonNB` class**: A Pelican reader that processes Jupyter notebooks, extracts metadata, and converts content to HTML.
3. **Metadata extraction**: Supports two methods:
   - Reading metadata from a companion `.nbdata` file
   - Extracting metadata from the first cell of the notebook (when `IPYNB_MARKUP_USE_FIRST_CELL` is enabled)
4. **HTML summary generation**: Implements custom HTML parsing to create summaries for notebooks.

The custom HTML parsers (`MyHTMLParser` and `HTMLTagStripper`) are used to generate article summaries that respect the HTML structure of the notebook output.

### Liquid Module (`liquid.py`)

This module implements a liquid tag that can be used to embed notebooks within Markdown content. Key components:

1. **Tag registration**: Registers the `notebook` tag with the liquid tags system.
2. **Content processing**: Parses the liquid tag parameters to determine the source notebook path and optional cell range.
3. **HTML generation**: Leverages the core module to convert the specified notebook to HTML content.

The liquid tag format is:
```
{% notebook path/to/notebook.ipynb [cells[start:end]] %}
```

### Vendor Package

The plugin includes bundled dependencies in the `vendor/` directory, primarily the `liquid_tags` implementation, to avoid external dependencies and provide a self-contained package.

## Integration with Pelican

### Markup Mode Integration

1. The `markup.py` module registers with Pelican's `initialized` signal.
2. When Pelican encounters an `.ipynb` file (configured via `MARKUP` setting), it uses the `IPythonNB` reader.
3. The reader extracts metadata from a `.nbdata` file or the notebook's first cell.
4. The notebook is converted to HTML using `nbconvert` and the core module utilities.
5. The resulting HTML is returned to Pelican for inclusion in the site generation.

### Liquid Tag Integration

1. The `liquid.py` module registers a custom liquid tag (`notebook`).
2. When Pelican processes a Markdown file with this tag, the plugin extracts the notebook path and optional cell range.
3. The notebook is converted to HTML using the core module.
4. The HTML content replaces the liquid tag in the final rendered content.

## Conversion Process

The notebook-to-HTML conversion flow:

1. Load and configure `nbconvert` exporters and preprocessors.
2. Apply any custom preprocessors (e.g., `SubCell` for extracting specific cells).
3. Run the HTML export process through `nbconvert`.
4. Process and clean the CSS to avoid theme conflicts.
5. Add custom scripts (e.g., MathJax configuration) to the generated HTML.
6. Generate a summary if configured (markup mode only).
7. Return the processed HTML content and metadata to Pelican.

## Configuration Options

The plugin provides numerous configuration options that can be set in Pelican's `pelicanconf.py` file:

### Common Options

- `IPYNB_FIX_CSS`: Controls CSS cleanup functionality
- `IPYNB_SKIP_CSS`: Skips including any notebook CSS
- `IPYNB_PREPROCESSORS`: Custom preprocessors for `nbconvert` to use
- `IPYNB_EXPORT_TEMPLATE`: Custom export template path

### Markup Mode Options

- `IPYNB_STOP_SUMMARY_TAGS`: HTML tags that stop summary generation
- `IPYNB_GENERATE_SUMMARY`: Whether to auto-generate summaries
- `IPYNB_EXTEND_STOP_SUMMARY_TAGS`: Additional tags to stop summary generation
- `IPYNB_NB_SAVE_AS`: Path pattern to save original notebooks
- `IPYNB_COLORSCHEME`: Pygments color scheme for syntax highlighting
- `IPYNB_MARKUP_USE_FIRST_CELL`: Use first cell for metadata extraction

## Extension Points

Developers interested in extending the plugin should consider these main extension points:

1. **Custom preprocessors**: Add custom notebook preprocessing by defining preprocessors and adding them to the `IPYNB_PREPROCESSORS` setting.
2. **Custom templates**: Create custom export templates and specify them with `IPYNB_EXPORT_TEMPLATE`.
3. **Custom CSS handling**: Modify the CSS processing in `parse_css()` to handle theme-specific issues.
4. **Additional metadata sources**: Extend the metadata extraction in the markup reader.

## Testing

The plugin includes tests in the `tests/` directory. The test structure:

1. **`test_base_usage.py`**: Tests the basic functionality of the plugin with different configurations.
2. **`test_import.py`**: Tests import functionality.
3. **Test data**: Sample notebooks and configuration files in the `tests/pelican/` directory.

Tests run Pelican with different configurations and verify that the expected output files are generated correctly.

## Compatibility Considerations

The plugin is designed to work with:
- Different Pelican versions (primarily 4.x)
- Different Jupyter/IPython/nbconvert versions
- Various themes and CSS frameworks

Compatibility is managed through:
- Try/except import blocks for different library versions
- CSS cleanup and isolation
- Configurable preprocessing options

## Performance Considerations

When working with large notebooks, developers should be aware of:

1. **Summary generation**: The HTML parsing for summary generation can be resource-intensive.
2. **CSS processing**: The CSS cleanup can add overhead to the generation process.
3. **Preprocessors**: Custom preprocessors can significantly impact conversion time.

## Conclusion

The `pelican-jupyter` plugin provides a flexible system for integrating Jupyter notebooks into Pelican-generated static sites. Developers can extend or modify the plugin by targeting the appropriate component for their needs, whether that's the core conversion process, metadata handling, or integration with Pelican.

By understanding the architecture and components described in this documentation, developers should have a solid foundation for maintaining, debugging, or extending the plugin functionality.