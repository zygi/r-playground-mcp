FROM docker.io/rocker/r2u:jammy

RUN apt update -qq && apt install -y curl

ENV PATH="/root/.local/bin:$PATH"

RUN (curl -LsSf https://astral.sh/uv/install.sh | sh) && uv --version

# Install tidyverse by default
RUN Rscript -e 'install.packages("tidyverse")'

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

RUN apt remove -y gcc-11 g++-11 cpp-11 && apt autoremove -y && rm -rf /var/lib/apt/lists/*

# Squash the image to reduce size
FROM scratch AS uv
COPY --from=0 / /
WORKDIR /app
ENV PATH="/root/.local/bin:$PATH"

# This seems to be necessary since for some reason just doing `uv run` forces a reinstall of the local editable package, which while almost instant outputs stuff to stdio, and we can't have that since the mcp uses stdio
CMD [ "bash", "-c", "uv sync --python=3.13 > /dev/null 2>&1 && uv run python -m rplayground_mcp.mcp_cli" ]


# ENTRYPOINT [ "uv", "run", "python", "-m", "rplayground_mcp.mcp_cli" ]