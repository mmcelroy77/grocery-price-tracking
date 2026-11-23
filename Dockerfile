# Image that runs one Dagster asset, by default the QFC egg snapshot, then exits.
# Build: docker build -t grocery-price-tracking .
# It has the Dagster CLI but not the web UI. Secrets (.env, AWS keys) are never baked in;
# pass them at run time. See "Container image" in README.md.

FROM eclipse-temurin:21-jre-noble

# Same uv version as uv.toml requires.
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

ENV PYTHONUNBUFFERED=1 \
    UV_PYTHON=/usr/bin/python3 \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
RUN chown app:app /app
USER app

# Dependencies first, so this big layer is reused until uv.lock changes.
COPY --chown=app pyproject.toml uv.lock uv.toml ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=app src ./src
RUN uv sync --frozen --no-dev --no-editable

# Download the Spark jars (Delta and the S3 connector) now, into ~/.ivy2.5.2, so each
# run starts without a ~600 MB download. The dummy key only makes configure() request
# the S3 connector; it is never used to connect to anything.
RUN python -c "from pyspark.sql import SparkSession; \
from grocery_price_tracking.spark import configure; \
builder = SparkSession.builder.master('local[1]').appName('prefetch-jars'); \
configure(builder, s3_conf={'spark.hadoop.fs.s3a.access.key': 'x'}).getOrCreate().stop()"

ENTRYPOINT ["dagster", "asset", "materialize", "-m", "grocery_price_tracking.orchestration.definitions"]
CMD ["--select", "kroger_bronze_products"]
