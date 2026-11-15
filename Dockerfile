FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# The validated 80 m grid (231 MB) is over GitHub's file limit, so a clone does not have it, and the
# public link must serve it: every example in the storyboard and the submission text is on that grid.
#   docker build --build-arg GRID80=1 -t slipday .     downloads NASA's file (189 MB, sha256 checked) and builds it
#   docker build -t slipday .                          uses whatever is in data/dem/: without the 80 m file the app
#                                                      runs on the 240 m grid, says so, and widens its landing scatter
# Measured in a container with two CPUs under scripts/stress_check.py: the 80 m grid peaks at 431 MB of the
# memory group inside a 512 MB limit and at 421 MB inside 1 GB; the 240 m grid at 299 MB.  An image that has
# the 80 m file can be run on the 240 m grid with -e SLIPDAY_SKIP_DEMS=ldem_80s_80m.
ARG GRID80=0
RUN if [ "$GRID80" = "1" ] && [ ! -f data/dem/ldem_80s_80m_f32.npy ]; then \
      python scripts/fetch_grid80.py && rm -f data/reference/LDEM_80S_80MPP_ADJ.TIF; fi
# glibc keeps freed memory in per-thread arenas; two arenas keep the resident size down on a small host.
# slipday/load.py applies the same limit in code if a start command forgets the variable.
ENV PORT=8000 MALLOC_ARENA_MAX=2
CMD ["sh", "-c", "exec uvicorn slipday.api:app --host 0.0.0.0 --port ${PORT}"]
