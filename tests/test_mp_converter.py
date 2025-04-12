import pytest
from pathlib import Path
from typing import AsyncGenerator

import pytest_asyncio

from rplayground_mcp.pdf_conversion.converter_subprocess_impl import MPMarkerConverter

DUMMY_PDF_PATH = Path(__file__).parent / "dummy.pdf"

pytestmark = [pytest.mark.slow]

@pytest_asyncio.fixture
async def converter() -> AsyncGenerator[MPMarkerConverter, None]:
    """Fixture that provides an initialized MPMarkerConverter and ensures cleanup."""
    converter = MPMarkerConverter()
    try:
        converter.start()
        # Wait for startup - adjust timeout as needed for your environment
        await converter.wait_for_startup(timeout=60.0)
        yield converter
    finally:
        await converter.async_shutdown()

@pytest.mark.asyncio
async def test_pdf_conversion(converter: MPMarkerConverter) -> None:
    """Test conversion of a PDF file."""
    assert DUMMY_PDF_PATH.exists(), f"Test file not found: {DUMMY_PDF_PATH}"
    
    # Convert the dummy PDF
    result = await converter.convert(DUMMY_PDF_PATH)
    
    # Basic validation of the result structure
    assert isinstance(result, dict)
    assert "text" in result
    assert "images" in result
    assert isinstance(result["text"], str)
    assert isinstance(result["images"], dict)
    
    # The actual content will depend on dummy.pdf, but we can verify it's not empty
    assert len(result["text"]) > 0
    # Depending on the PDF, it might or might not have images
    # Just check that the structure is as expected
    for page_idx, img_base64 in result["images"].items():
        assert isinstance(page_idx, int)
        assert isinstance(img_base64, str)
        assert len(img_base64) > 0

@pytest.mark.asyncio
async def test_multiple_conversions(converter: MPMarkerConverter) -> None:
    """Test that multiple conversions can be performed with the same converter."""
    for _ in range(2):  # Run conversion twice
        result = await converter.convert(DUMMY_PDF_PATH)
        assert isinstance(result, dict)
        assert "text" in result
        assert len(result["text"]) > 0 