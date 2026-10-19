import sys
from unittest.mock import MagicMock

# pdf_extraction imports pdfplumber at load time. Tests supply tables
# through a fake open(); a real PDF is not required.
sys.modules.setdefault("pdfplumber", MagicMock())
