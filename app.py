"""Compatibility entry point for the Gradio application.

Initialize data once with ``python -m scripts.init_database`` and build the
offline vector index with ``python -m scripts.build_index --provider hash``.
"""

from ui.gradio_app import main

if __name__ == "__main__":
    main()
