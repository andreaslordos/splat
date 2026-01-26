# Sphinx configuration file

project = "Splat"
copyright = "2025, Andreas Lordos"
author = "Andreas Lordos"

extensions = [
    "myst_parser",
    "sphinx_copybutton",
]

# MyST settings for Markdown support
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "plans", "skills"]

# Theme
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "navigation_depth": 3,
    "collapse_navigation": False,
}

# Source file settings
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
