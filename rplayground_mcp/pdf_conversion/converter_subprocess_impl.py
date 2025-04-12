import multiprocessing
import sys
import io
import logging
import base64
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, cast
import multiprocessing.synchronize
import multiprocessing.pool
from rplayground_mcp.pdf_conversion.converter_subprocess import ConversionResult, MarkerConverter

if TYPE_CHECKING:
    from marker.converters.pdf import PdfConverter


logger = logging.getLogger(__name__)


# Worker process state
worker_converter: 'PdfConverter | None' = None
worker_init_exception: Exception | None = None


def _init_worker(startup_event: multiprocessing.synchronize.Event) -> None:
    global worker_converter, worker_init_exception
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    
    original_stdout = sys.stdout
    output = io.StringIO()
    sys.stdout = output
    try:
        worker_converter = PdfConverter(artifact_dict=create_model_dict())
    except Exception as e:
        worker_init_exception = e
        logger.exception("Worker initialization failed")
    finally:
        sys.stdout = original_stdout
        startup_event.set()

def _warmup() -> None:
    # Placeholder for potential future warmup logic if needed
    pass

def _convert_pdf(pdf_path_str: str) -> ConversionResult:
    from marker.output import text_from_rendered
    from rplayground_mcp import utils
    import PIL.Image

    global worker_converter, worker_init_exception

    if worker_init_exception:
        # Propagate the initialization error to the main process
        raise RuntimeError("Worker failed to initialize") from worker_init_exception
    if worker_converter is None:
        # This should ideally not happen if initialization logic is correct
        raise RuntimeError("Converter is not initialized in worker")

    pdf_path = Path(pdf_path_str)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path_str}")

    rendered = worker_converter(str(pdf_path.resolve()))
    text, _, images = text_from_rendered(rendered)

    def get_image_base64(img: PIL.Image.Image) -> str:
        with io.BytesIO() as buffer:
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    image_values = {
        idx: get_image_base64(utils.assertType(img, PIL.Image.Image))
        for idx, img in images.items()
    }

    return {"text": text, "images": image_values}


class MPMarkerConverter(MarkerConverter):
    def __init__(self) -> None:
        self._pool: multiprocessing.pool.Pool | None = None
        self._startup_event: multiprocessing.synchronize.Event | None = None
        self._executor = None # Use default executor

    # Make start synchronous
    def start(self) -> None:
        if self._pool is not None:
            return

        self._startup_event = multiprocessing.Event()
        
        # Creating the pool is blocking, do it directly
        self._pool = multiprocessing.Pool(
            processes=1,
            initializer=_init_worker,
            initargs=(self._startup_event,)
        )
        
        # issue a warmup request but don't wait for it
        # apply_async is non-blocking
        self._pool.apply_async(_warmup)

    async def wait_for_startup(self, timeout: float | None = None) -> bool:
        if self._startup_event is None or self._pool is None:
            raise RuntimeError("Converter pool not started")

        loop = asyncio.get_running_loop()
        try:
            # Event.wait() is blocking
            ready = await loop.run_in_executor(
                self._executor, self._startup_event.wait, timeout
            )
            if not ready:
                await self.async_shutdown(timeout=1.0)
                raise TimeoutError("Converter startup timed out")
            # Check for worker init exception after event is set
            if worker_init_exception:
                 await self.async_shutdown(timeout=1.0)
                 raise RuntimeError("Worker failed to initialize during startup") from worker_init_exception
            return ready
        except Exception:
             await self.async_shutdown(timeout=1.0)
             raise


    async def convert(self, pdf_path: Path, timeout: float = 300.0) -> ConversionResult:
        if self._pool is None:
            raise RuntimeError("Converter pool not running")
        # Add assertion for type checker
        assert self._pool is not None
        pool = self._pool # Use local variable after check

        if not pdf_path.is_file():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        loop = asyncio.get_running_loop()
        
        # apply_async might block briefly, but get() is definitely blocking
        # Explicitly cast pool to satisfy the linter
        pool = cast(multiprocessing.pool.Pool, pool)
        async_result = await loop.run_in_executor(
            self._executor, pool.apply_async, _convert_pdf, (str(pdf_path),) # type: ignore[union-attr]
        )
        
        try:
             # Wait for the result from the worker process asynchronously
            result = await loop.run_in_executor(
                self._executor, async_result.get, timeout
            )
            # Basic check for the expected structure
            if isinstance(result, dict) and "text" in result and "images" in result:
                return cast(ConversionResult, result)
            else:
                # This case indicates an unexpected return value from the worker
                raise TypeError(f"Unexpected result type from worker: {type(result)}")
        except multiprocessing.TimeoutError:
            logger.error(f"Conversion timed out for {pdf_path}")
            await self.async_shutdown(timeout=1.0) # Attempt graceful shutdown
            raise TimeoutError(f"Conversion timed out for {pdf_path}")
        except Exception as e:
            # Catch other potential errors during result retrieval or from the worker
            logger.exception(f"Error during conversion of {pdf_path}")
            await self.async_shutdown(timeout=1.0) # Attempt graceful shutdown
            raise RuntimeError(f"Conversion failed for {pdf_path}") from e

    async def async_shutdown(self, timeout: float = 5.0) -> None:
        """Asynchronously shuts down the worker pool."""
        if self._pool is None:
            return
            
        loop = asyncio.get_running_loop()
        pool_to_shutdown = self._pool
        self._pool = None # Prevent further use
        self._startup_event = None

        try:
            await loop.run_in_executor(self._executor, pool_to_shutdown.close)
            await loop.run_in_executor(self._executor, pool_to_shutdown.join) # No timeout arg for join, handled by executor if needed
        except Exception as e:
            logger.warning(f"Error during graceful pool shutdown: {e}, attempting terminate.")
            try:
                await loop.run_in_executor(self._executor, pool_to_shutdown.terminate)
                await loop.run_in_executor(self._executor, pool_to_shutdown.join)
            except Exception as term_e:
                logger.error(f"Error during pool termination: {term_e}")
        finally:
             # Ensure pool reference is cleared even if shutdown fails
             if self._pool is pool_to_shutdown: # Check if it wasn't reset already
                 self._pool = None
                 self._startup_event = None
