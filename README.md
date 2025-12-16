# PowerPoint Inverter

Streamlit app that inverts slide decks (colors and images) using python-pptx and Pillow.

## Quickstart (uv)
```bash
uv run streamlit run main.py --server.address=0.0.0.0 --server.port=8501
```

## Docker
```bash
docker build -t pp .
docker run -p 8501:8501 pp
```

### Performance toggles
- The app uses a small bounded executor (2 workers max) for file-level work.
- Default uses `ProcessPoolExecutor`; on small VPS you can force threads to reduce memory:
  ```bash
  docker run -e PP_FORCE_THREADS=1 -p 8501:8501 pp
  ```

## Benchmarking
Run on real fixtures; scale up with copies/target-count:
```bash
uv run python bench.py --repeat 2
uv run python bench.py --target-count 100 --repeat 2  # ~100 files
```

## Notes
- JPEG output quality is 85 for speed; PNG is used automatically when transparency is present.
- Dependency management is via `uv`; Docker image is built with a multi-stage `uv` workflow.
