# FROM docker.io/posit/r-base:4.4-focal
# FROM docker.io/posit/r-base:4.4-focal

# FROM rstudio/rstudio-package-manager:ubuntu2204
FROM docker.io/rocker/r2u:focal

RUN apt update -qq && apt install -y curl build-essential wget git libzstd-dev

ENV PATH="/root/.local/bin:$PATH"

RUN (curl -LsSf https://astral.sh/uv/install.sh | sh) && uv --version

COPY <<EOF /tmp/install_packages.R
# Install ctv package for task views
install.packages("ctv")

# Install metapackages
install.packages(c("tidyverse", "tidymodels"))

# Install specific task views
ctv::install.views(c(
#   "MachineLearning", 
  "Econometrics", 
  "TimeSeries", 
  "Bayesian",
  "NaturalLanguageProcessing",
  "ReproducibleResearch",
  "Finance"
))

# Install additional essential packages not covered by the above
install.packages(c(
  "data.table", "plotly", "shiny", "Rcpp", "knitr", "rmarkdown",
  "flexdashboard", "profvis", "quantmod", "glmnet", "xgboost", 
  "readxl", "haven", "odbc", "DT", "htmlwidgets", "leaflet"
))
EOF
ARG PREINSTALL_PACKAGES=false 

RUN if [ "$PREINSTALL_PACKAGES" = true ]; then Rscript /tmp/install_packages.R; fi

COPY . /app
WORKDIR /app

RUN uv sync --python=3.13


# This seems to be necessary since for some reason just doing `uv run` forces a reinstall of the local editable package, which while almost instant outputs stuff to stdio, and we can't have that since the mcp uses stdio
ENTRYPOINT [ "bash", "-c", "uv sync --python=3.13 > /dev/null 2>&1 && uv run python -m rplayground_mcp.mcp_cli" ]


# ENTRYPOINT [ "uv", "run", "python", "-m", "rplayground_mcp.mcp_cli" ]