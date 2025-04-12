import logging
from typing import Any, Type, TypeVar
import rpy2.situation
from rpy2.robjects import r

logger = logging.getLogger(__name__)


def get_r_situation():
    situation_string = "\n".join(
        [x if x is not None else "None" for x in list(rpy2.situation.iter_info())]
    )
    return situation_string


def get_r_available_packages() -> list[str]:
    """Lists all packages installed in R."""

    # Get list of installed packages using R's installed.packages() function
    try:
        # Get the matrix of installed packages
        packages_matrix = r("installed.packages()")
        # Extract the first column which contains package names
        package_names = list(packages_matrix.rx(True, 1))  # type: ignore
        return [str(pkg) for pkg in package_names]
    except Exception as e:
        # Return empty list if there's an error
        logger.error("Error getting installed packages: %s", str(e), exc_info=True)
        return []


T = TypeVar("T")


def assertType(x: Any, t: Type[T]) -> T:
    if not isinstance(x, t):
        raise ValueError(f"Expected {t}, got {type(x)}")
    return x


if __name__ == "__main__":
    print(get_r_available_packages())
    print(get_r_situation())
