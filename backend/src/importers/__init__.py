"""Universal course importer: platform detection, safe retrieval, structure-preserving extraction."""
from .fetch import FetchError, Fetcher, validate_url
from .pipeline import canonical, run_import
from .platforms import detect, extractor_for
